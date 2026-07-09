#!/usr/bin/env python3
"""ziptie 컴팩션 프리플라이트 프로브 (기술 스파이크, dev 전용).

pty로 대화형 `claude` 세션을 띄우고, require-read 룰을 한 번 발화시켜 배달
마커를 만든 뒤 `/compact`를 보내 실제 컴팩션을 유도하고, ziptie의
SessionStart(compact) 훅이 마커를 리셋(재무장)하는지 디스크 상태(state
마커 파일 + JSONL 로그)로 검증한다.

사용법:
    uv run --with pexpect python3 pilot/compact_probe.py

전제: `claude` CLI가 이미 로그인되어 있고(headless -p 실행이 가능한 상태),
저장소 루트가 /Users/yuseobshim/Projects/ziptie 이다 (경로는 스크립트 위치
기준으로 자동 계산됨).

TUI는 ANSI 노이즈가 심해서 화면 파싱으로 "응답 완료"를 판정하지 않는다.
대신 (a) 유휴 타임아웃(idle timeout) — 일정 시간 새 바이트가 없으면
응답이 끝난 것으로 간주하고, (b) 디스크에 남는 부작용(state 마커 파일,
.claude/ziptie/logs/*.jsonl) — 을 그라운드 트루스로 쓴다. 이 두 방법을
병행한다: idle 타임아웃으로 "다음 입력을 보내도 되는 시점"을 잡고, 최종
판정은 항상 디스크 상태로 한다.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time

try:
    import pexpect
except ImportError:
    print(
        "pexpect가 없다. `uv run --with pexpect python3 pilot/compact_probe.py`로 실행할 것.",
        file=sys.stderr,
    )
    sys.exit(1)

PILOT_DIR = os.path.dirname(os.path.abspath(__file__))
ZIPTIE_ROOT = os.path.dirname(PILOT_DIR)
SANDBOX = os.path.join(PILOT_DIR, "runs", "PROBE-1")
CAPTURE_DIR = os.path.join(PILOT_DIR, "runs", "PROBE-1-capture")
STATE_DIR = os.path.join(SANDBOX, ".claude", "ziptie", "state")
LOG_DIR = os.path.join(SANDBOX, ".claude", "ziptie", "logs")
TRANSCRIPT_PATH = os.path.join(PILOT_DIR, "runs", "PROBE-1-transcript.log")

RULE_TRIGGER_CMD = 'gh pr create --title "ziptie probe" --body "probe body"'
TRIGGER_MSG = (
    "Bash 도구로 정확히 다음 명령어를 그대로 실행해(다른 명령은 실행하지 마): "
    + RULE_TRIGGER_CMD
)
FILLER_MSGS = [
    "src/greet.ts 파일을 읽고 함수 시그니처만 한 줄로 답해.",
    "docs/pr-rules.md 파일을 읽고 섹션 제목만 나열해.",
]

ANSI_RE = re.compile(rb"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07")
# TUI가 커서 이동 시퀀스(\x1b[NG)로 단어 사이를 끊어 렌더링하기 때문에,
# ANSI_RE로 스트립한 뒤에도 단어 사이 공백이 사라져 "Doyouwanttoproceed?"
# 형태가 된다. 그래서 \s*로 토큰 사이 공백 유무를 모두 허용한다.
CONFIRM_RE = re.compile(rb"Do\s*you\s*want\s*to\s*proceed", re.IGNORECASE)

results = {}  # criterion -> (bool, detail str)


def log(msg):
    print(f"[probe] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 샌드박스 준비 (pilot/run.sh의 Z 조건 패턴을 따름: template/repo 복사,
# settings-A.json 허용 목록, .claude/rules/ 배치, 신뢰 워크스페이스 등록)
# ---------------------------------------------------------------------------


def setup_sandbox():
    log(f"샌드박스 준비: {SANDBOX}")
    shutil.rmtree(SANDBOX, ignore_errors=True)
    shutil.rmtree(CAPTURE_DIR, ignore_errors=True)
    if os.path.exists(TRANSCRIPT_PATH):
        os.remove(TRANSCRIPT_PATH)
    os.makedirs(os.path.dirname(SANDBOX), exist_ok=True)
    shutil.copytree(os.path.join(PILOT_DIR, "template", "repo"), SANDBOX)
    os.makedirs(CAPTURE_DIR, exist_ok=True)

    # B 조건 전용 스크립트는 지운다 (settings에서 참조 안 함, run.sh와 동일 패턴)
    inject = os.path.join(SANDBOX, ".claude", "hooks", "inject.py")
    if os.path.exists(inject):
        os.remove(inject)

    shutil.copy(
        os.path.join(PILOT_DIR, "template", "settings-A.json"),
        os.path.join(SANDBOX, ".claude", "settings.json"),
    )
    os.makedirs(os.path.join(SANDBOX, ".claude", "rules"), exist_ok=True)
    shutil.copy(
        os.path.join(PILOT_DIR, "template", "rules-pr.md"),
        os.path.join(SANDBOX, ".claude", "rules", "pr-rules.md"),
    )

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=SANDBOX, check=True)
    subprocess.run(["git", "add", "-A"], cwd=SANDBOX, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=lab@test",
            "-c",
            "user.name=lab",
            "commit",
            "-q",
            "-m",
            "initial commit",
        ],
        cwd=SANDBOX,
        check=True,
    )

    # 신뢰 워크스페이스 등록 — 미등록 시 settings.json이 무시된다 (run.sh와 동일)
    claude_json = os.path.expanduser("~/.claude.json")
    with open(claude_json) as f:
        conf = json.load(f)
    conf.setdefault("projects", {}).setdefault(SANDBOX, {})[
        "hasTrustDialogAccepted"
    ] = True
    with open(claude_json, "w") as f:
        json.dump(conf, f, indent=2)


# ---------------------------------------------------------------------------
# pty 드라이버
# ---------------------------------------------------------------------------


class Session:
    def __init__(self):
        env = os.environ.copy()
        env["PATH"] = f"{os.path.join(PILOT_DIR, 'mock-bin')}:" + env["PATH"]
        env["GH_CAPTURE_DIR"] = CAPTURE_DIR
        self.logf = open(TRANSCRIPT_PATH, "wb")
        cmd = f'claude --plugin-dir "{ZIPTIE_ROOT}"'
        log(f"스폰: {cmd} (cwd={SANDBOX})")
        self.child = pexpect.spawn(
            cmd, cwd=SANDBOX, env=env, timeout=None, encoding=None, dimensions=(50, 200)
        )
        self.child.logfile = self.logf

    def send_msg(self, text, settle=0.5):
        """텍스트 전송 후 살짝 대기하고 나서 Enter를 별도로 보낸다.

        text+"\\r"을 한 번에 보내면 TUI가 이를 붙여넣기로 인식해 제출이
        되지 않는 경우가 있었다 (탐색 중 재현됨) — 그래서 두 단계로 분리.
        """
        self.child.send(text)
        time.sleep(settle)
        self.child.send("\r")

    def wait_idle(self, idle=4.0, max_wait=150.0, poll=0.3):
        """유휴 타임아웃 기반 '응답 완료' 감지 + '진행하시겠습니까?' 류
        확인창은 기본값(Enter=예)으로 자동 응답한다."""
        start = time.time()
        last_data = time.time()
        buf = b""
        confirmed_lens = set()
        while True:
            try:
                data = self.child.read_nonblocking(size=65536, timeout=poll)
                if data:
                    last_data = time.time()
                    buf += data
            except pexpect.exceptions.TIMEOUT:
                pass
            except pexpect.exceptions.EOF:
                log("EOF — 세션이 이미 종료됨")
                break
            now = time.time()
            clean = ANSI_RE.sub(b"", buf)
            if CONFIRM_RE.search(clean) and len(clean) not in confirmed_lens:
                confirmed_lens.add(len(clean))
                log("확인창 감지 — Enter(기본값 Yes)로 자동 응답")
                time.sleep(0.3)
                self.child.send("\r")
                last_data = time.time()
                buf = b""
                continue
            if now - last_data > idle:
                return True
            if now - start > max_wait:
                log(f"max_wait({max_wait}s) 초과 — idle 감지 포기하고 진행")
                return False

    def close(self):
        try:
            self.child.sendcontrol("c")
            time.sleep(0.5)
            self.child.sendcontrol("c")
            time.sleep(0.5)
        except Exception:
            pass
        self.child.close(force=True)
        self.logf.close()


def list_state():
    return sorted(os.listdir(STATE_DIR)) if os.path.isdir(STATE_DIR) else []


def read_log_entries():
    entries = []
    if not os.path.isdir(LOG_DIR):
        return entries
    for fn in sorted(os.listdir(LOG_DIR)):
        with open(os.path.join(LOG_DIR, fn)) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries


def poll_until(predicate, timeout=60.0, interval=1.0):
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


# ---------------------------------------------------------------------------
# 메인 시퀀스
# ---------------------------------------------------------------------------


def main():
    setup_sandbox()
    sess = Session()
    t_total0 = time.time()
    # wait_idle()의 반환값(자연 idle=True vs max_wait 강제종료=False)을
    # 턴별로 모아서 기준 1 판정에 반영한다 (초기 렌더링 대기는 "프롬프트
    # 전송"이 아니므로 제외).
    idle_results = []
    try:
        log("초기 렌더링 대기")
        sess.wait_idle(idle=2.0, max_wait=20.0)

        # ① 룰 트리거 과제 전송 → 배달 마커 생성 유도
        log("① 룰 트리거 과제 전송")
        t0 = time.time()
        sess.send_msg(TRIGGER_MSG)
        idle_results.append(("turn1_trigger", sess.wait_idle(idle=4.0, max_wait=120.0)))
        elapsed1 = time.time() - t0
        marker_before = [f for f in list_state() if f.endswith("--pr-rules")]
        deny_before = [e for e in read_log_entries() if e.get("decision") == "deny"]
        marker_ok = bool(marker_before) and bool(deny_before)
        results["3a_pre_compact_marker"] = (
            marker_ok,
            f"state 마커={marker_before}, deny 로그={len(deny_before)}건",
        )
        log(f"turn1 완료 ({elapsed1:.1f}s) marker_before={marker_before}")

        # 패딩 — 대화가 너무 짧으면 /compact가 거부할 수 있음
        for i, fm in enumerate(FILLER_MSGS, start=2):
            log(f"filler turn {i}")
            sess.send_msg(fm)
            idle_results.append(
                (f"filler_turn{i}", sess.wait_idle(idle=4.0, max_wait=90.0))
            )

        # ② /compact 전송
        log("② /compact 전송")
        t0 = time.time()
        sess.send_msg("/compact")
        idle_results.append(("compact", sess.wait_idle(idle=5.0, max_wait=150.0)))

        # ③ 컴팩션 완료 + rearm 로그 대기 (idle 감지가 일러도 디스크 상태로 재확인)
        def rearm_seen():
            return any(e.get("decision") == "rearm" for e in read_log_entries())

        poll_until(rearm_seen, timeout=90.0, interval=2.0)
        elapsed_compact = time.time() - t0
        log(f"/compact 처리 총 소요 {elapsed_compact:.1f}s")

        entries_after_compact = read_log_entries()
        rearm_entries = [
            e for e in entries_after_compact if e.get("decision") == "rearm"
        ]
        marker_after = [f for f in list_state() if f.endswith("--pr-rules")]

        c2_ok = bool(
            rearm_entries
        )  # rearm은 오직 SessionStart(source=compact) 발화 시에만 기록됨
        results["2_compaction_occurred"] = (
            c2_ok,
            f"/compact 소요 {elapsed_compact:.1f}s, rearm 로그 존재={c2_ok} "
            "(rearm은 실제 컴팩션 시에만 SessionStart(compact)가 쏘는 신호이므로 "
            "컴팩션 발생의 간접 증거)",
        )
        c3_ok = (
            c2_ok
            and not marker_after
            and any(e.get("count", 0) >= 1 for e in rearm_entries)
        )
        results["3_sessionstart_compact_rearm"] = (
            c3_ok,
            f"rearm 엔트리={rearm_entries}, 컴팩션 후 남은 pr-rules 마커={marker_after}",
        )

        # ④ 재트리거 — 재배달 확인 (선택 사항이지만 강한 증거)
        log("④ 재트리거 (재배달 확인)")
        deny_count_before_retrigger = len(
            [e for e in entries_after_compact if e.get("decision") == "deny"]
        )
        sess.send_msg(TRIGGER_MSG)
        idle_results.append(("retrigger", sess.wait_idle(idle=4.0, max_wait=120.0)))
        entries_final = read_log_entries()
        deny_count_after_retrigger = len(
            [e for e in entries_final if e.get("decision") == "deny"]
        )
        marker_redelivered = [f for f in list_state() if f.endswith("--pr-rules")]
        redelivery_ok = (
            deny_count_after_retrigger > deny_count_before_retrigger
            and bool(marker_redelivered)
        )
        results["4_redelivery_after_rearm"] = (
            redelivery_ok,
            f"재배달 마커={marker_redelivered}, deny 로그 {deny_count_before_retrigger}->{deny_count_after_retrigger}",
        )

        # 기준 1 — 모든 턴이 자연 idle(=True)로 완료됐는지 판정. max_wait으로
        # 강제 종료된 턴이 하나라도 있으면 FAIL로 기록한다 (idle-timeout이
        # "응답 완료"를 제대로 감지하지 못했다는 신호이므로).
        forced = [label for label, ok in idle_results if not ok]
        c1_ok = len(idle_results) > 0 and not forced
        results["1_prompt_and_completion_detected"] = (
            c1_ok,
            f"turn1 소요 {elapsed1:.1f}s, 턴별 idle 판정={idle_results}, "
            f"강제타임아웃 턴={forced if forced else '없음'}",
        )

        # ⑤ 종료
        log("⑤ 세션 종료")
    finally:
        sess.close()

    total_elapsed = time.time() - t_total0
    log(f"전체 소요 {total_elapsed:.1f}s")

    print("\n=== 결과 요약 ===")
    all_core_pass = True
    for key in [
        "1_prompt_and_completion_detected",
        "3a_pre_compact_marker",
        "2_compaction_occurred",
        "3_sessionstart_compact_rearm",
        "4_redelivery_after_rearm",
    ]:
        ok, detail = results.get(key, (False, "미실행"))
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {key}: {detail}")
        if key in (
            "1_prompt_and_completion_detected",
            "2_compaction_occurred",
            "3_sessionstart_compact_rearm",
        ):
            all_core_pass = all_core_pass and ok

    print(f"\n총 소요 시간: {total_elapsed:.1f}s")
    print(f"transcript: {TRANSCRIPT_PATH}")
    print(f"state dir 최종: {list_state()}")
    print(f"log 최종: {read_log_entries()}")

    sys.exit(0 if all_core_pass else 1)


if __name__ == "__main__":
    main()
