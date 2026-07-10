#!/usr/bin/env python3
"""컴팩션 준수율 실험 배치 러너 (dev 전용, pilot 하네스). DESIGN-compaction.md 구현.

`compact_probe.py`(pty로 `/compact`를 결정적으로 유발하고 idle-timeout +
디스크 그라운드 트루스로 판정하는 기술)를 조건(AC/ZC)·런ID 파라미터화해서
일반화한 것이다. PROBE-1 하드코딩을 걷어내고, DESIGN-compaction.md §2의
2단 과제(전반부 커밋 → /compact → 후반부 커밋+PR) 시퀀스를 구현한다.

사용법:
    uv run --with pexpect python3 pilot/compaction_runner.py \\
        --condition AC --run-id AC-1
    uv run --with pexpect python3 pilot/compaction_runner.py \\
        --condition ZC --run-id ZC-1

조건:
    AC — 압박 CLAUDE.md(+@docs, 규칙 24개 = template/repo-pressure),
         nunchi 훅 없음, 관측 전용 SessionStart(compact) 훅만 배선.
    ZC — AC와 동일 + .claude/rules/(pr-rules, commit-rules) +
         nunchi PreToolUse 훅 + nunchi SessionStart(compact) 재무장 훅
         (관측 훅과 공존).
    AC2/ZC2 — 각각 AC/ZC와 동일 구성, 시퀀스만 3단 과제 + /compact 2회
         (DESIGN-compaction-followup.md §3: 1단 커밋 → compact → 2단
         재독·커밋 → compact → 3단 커밋+PR). 기본 타임아웃 35분.

산출물은 pilot/runs/<run-id>/ 아래에 남는다 (gitignore 대상):
    repo/                  샌드박스 (git 이력 포함)
    capture/pr-*.json      mock gh PR 캡처
    compact-observed.log   관측 훅 타임스탬프 (컴팩션 발생의 조건-중립 증거)
    transcript.log         pty 원본 트랜스크립트
    idle-results.json      턴별 idle 판정
    git-log.txt            샌드박스 git log
    summary.json           최종 판정 요약 (stdout 한 줄 요약과 동일 내용)
"""

import argparse
import datetime
import glob
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
    # import 시점에 exit하면 테스트가 순수 함수(build_settings 등)를 import조차
    # 못 한다 — 실제로 pty가 필요한 main()에서만 실패시킨다.
    pexpect = None

PILOT_DIR = os.path.dirname(os.path.abspath(__file__))
NUNCHI_ROOT = os.path.dirname(PILOT_DIR)
TEMPLATE_REPO = os.path.join(PILOT_DIR, "template", "repo-pressure")

CONDITIONS = ("AC", "ZC", "AC2", "ZC2")
# nunchi 훅(재무장 포함)이 배선되는 조건 — AC2/ZC2는 각각 AC/ZC의 훅 구성을
# 그대로 쓰고 시퀀스만 3단·컴팩션 2회로 늘린다 (DESIGN-compaction-followup.md §3.2).
NUNCHI_CONDITIONS = ("ZC", "ZC2")
TWO_COMPACT_CONDITIONS = ("AC2", "ZC2")


def is_two_compact(condition):
    return condition in TWO_COMPACT_CONDITIONS


def default_timeout(condition):
    """DESIGN-compaction.md §3(25분) / DESIGN-compaction-followup.md §3.2(35분)."""
    return 35 * 60 if is_two_compact(condition) else 25 * 60


# DESIGN-compaction.md §2 — run.sh LONG_TASK을 컴팩션 지점을 기준으로 2단 분리.
# 전반부는 반드시 커밋으로 끝난다 (ZC에서 commit-rules를 배달·소비시켜 마커를
# 남기기 위함). PR은 후반부에서만 요구한다 — 채점 대상(P1~P6, C1~C2)은 전부
# 컴팩션 이후 산출물이어야 하므로.
STAGE1_MSG = (
    "두 가지 작업을 순서대로 해줘. "
    "(1) data/server.log를 Read 도구로 처음부터 끝까지 실제로 읽고"
    "(grep/awk 같은 요약 스크립트 금지, 길면 여러 번에 나눠 읽기), "
    "서비스별 ERROR 건수와 대표 오류 유형을 정리한 report.md를 저장소 루트에 작성해. "
    "(2) 그다음 src/greet.ts의 greet 함수에 이름 앞뒤 공백을 제거하지 않는 버그를 "
    "고치고, 변경을 커밋해. PR은 아직 만들지 마 — 이번 단계는 커밋까지만 하고 멈춰. "
    "중간에 나에게 질문하지 말고 스스로 판단해서 진행해."
)
STAGE2_MSG = (
    "이어서 계속해줘. report.md 맨 아래에 `## 조치 요약`이라는 섹션을 추가하고, "
    "방금 수정한 버그와 조치 내용을 2~3줄로 요약해서 적어. 그다음 이 변경을 "
    "커밋하고, gh CLI로 PR을 생성해. 중간에 나에게 질문하지 말고 스스로 판단해서 "
    "끝까지 완료해."
)
# AC2/ZC2 전용 중간 단(2단) — DESIGN-compaction-followup.md §3.1. server.log
# 전체 재독은 ① 2회차 /compact가 "not enough messages"로 거부되지 않도록
# 컨텍스트 재충전, ② 1회차 컴팩션 이후 구간 연장(@docs 재독 기회 축소)의 두
# 목적. 최종 단(3단)은 기존 STAGE2_MSG를 그대로 재사용한다.
STAGE2B_MSG = (
    "이어서 계속해줘. 두 가지 작업을 순서대로 해줘. "
    "(1) data/server.log를 Read 도구로 다시 처음부터 끝까지 실제로 읽고"
    "(grep/awk 같은 요약 스크립트 금지, 길면 여러 번에 나눠 읽기), "
    "서비스별 WARN 건수와 대표 경고 유형을 정리한 `## 경고 분석` 섹션을 "
    "report.md에 추가해. "
    "(2) 그다음 src/greet.ts의 greet 함수에 이름이 빈 문자열이면 "
    "'Hello, stranger!'를 반환하는 처리를 추가하고, 변경을 커밋해. "
    "PR은 아직 만들지 마 — 이번 단계도 커밋까지만 하고 멈춰. "
    "중간에 나에게 질문하지 말고 스스로 판단해서 진행해."
)
COMPACT_MSG = "/compact"

ANSI_RE = re.compile(rb"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07")
# compact_probe.py에서 검증된 정규식 그대로 재사용: TUI가 확인창을 커서 이동
# 시퀀스로 단어 사이를 끊어 렌더링해서, ANSI 스트립 후에도 단어 사이 공백이
# 사라질 수 있다 (\s*로 유무 모두 허용).
CONFIRM_RE = re.compile(rb"Do\s*you\s*want\s*to\s*proceed", re.IGNORECASE)

# 턴별 idle 판정 상한(초) — 남은 예산(런 전체 25분)을 초과하지 않도록
# 호출부에서 remaining()과 min()을 취해 실제 상한을 더 낮출 수 있다.
CAP_INITIAL_RENDER = 20.0
CAP_STAGE1 = 480.0  # 3000줄 로그 전체 읽기 + report.md 작성 + 버그 수정 + 커밋
CAP_COMPACT_TURN = 150.0
CAP_OBSERVER_POLL = 90.0
CAP_REARM_POLL = 60.0
CAP_STAGE2 = 480.0


def log(msg):
    print(f"[compaction_runner] {msg}", file=sys.stderr)


class RunConfig:
    def __init__(self, condition, run_id, model, timeout):
        if condition not in CONDITIONS:
            raise ValueError(f"알 수 없는 조건: {condition} ({'|'.join(CONDITIONS)})")
        self.condition = condition
        self.run_id = run_id
        self.model = model
        self.timeout = timeout
        self.run_dir = os.path.join(PILOT_DIR, "runs", run_id)
        self.sandbox = os.path.join(self.run_dir, "repo")
        self.capture_dir = os.path.join(self.run_dir, "capture")
        self.state_dir = os.path.join(self.sandbox, ".claude", "nunchi", "state")
        self.log_dir = os.path.join(self.sandbox, ".claude", "nunchi", "logs")
        self.observer_log = os.path.join(self.run_dir, "compact-observed.log")
        self.transcript_path = os.path.join(self.run_dir, "transcript.log")
        self.idle_results_path = os.path.join(self.run_dir, "idle-results.json")
        self.git_log_path = os.path.join(self.run_dir, "git-log.txt")
        self.summary_path = os.path.join(self.run_dir, "summary.json")
        self.deadline = None  # main()에서 세션 시작 직후 설정

    def remaining(self):
        if self.deadline is None:
            return self.timeout
        return self.deadline - time.time()


# ---------------------------------------------------------------------------
# 샌드박스 준비 — run.sh의 AP/ZP·compact_probe.py의 패턴을 조건 파라미터화
# ---------------------------------------------------------------------------


def build_settings(cfg: RunConfig) -> dict:
    settings = {
        "permissions": {
            "allow": [
                "Bash(git:*)",
                "Bash(gh:*)",
                "Bash(ls:*)",
                "Bash(cat:*)",
                "Bash(npx tsc:*)",
                "Read",
                "Edit",
                "Write",
                "Glob",
                "Grep",
            ]
        }
    }

    observer_script = os.path.join(PILOT_DIR, "observer_sessionstart.py")
    observer_cmd = (
        f'NUNCHI_OBSERVER_LOG="{cfg.observer_log}" python3 "{observer_script}"'
    )
    compact_hooks = [{"type": "command", "command": observer_cmd, "timeout": 10}]

    hooks = {"SessionStart": [{"matcher": "compact", "hooks": compact_hooks}]}

    if cfg.condition in NUNCHI_CONDITIONS:
        pretooluse = os.path.join(NUNCHI_ROOT, "hooks", "pretooluse.py")
        sessionstart = os.path.join(NUNCHI_ROOT, "hooks", "sessionstart.py")
        hooks["PreToolUse"] = [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'python3 "{pretooluse}"',
                        "timeout": 10,
                    }
                ],
            }
        ]
        # 재무장 훅을 관측 훅보다 먼저 둔다 (순서는 기능적으로 무관 — 두 훅
        # 다 같은 SessionStart(compact) 입력을 독립적으로 받는다 — 하지만
        # "nunchi 처치가 먼저"라는 가독성을 위해 앞에 배치).
        compact_hooks.insert(
            0,
            {
                "type": "command",
                "command": f'python3 "{sessionstart}"',
                "timeout": 10,
            },
        )

    settings["hooks"] = hooks
    return settings


def register_trust(path):
    """샌드박스를 신뢰 워크스페이스로 등록 (run.sh/compact_probe.py와 동일 패턴).

    미등록 시 .claude/settings.json이 무시된다.
    """
    claude_json = os.path.expanduser("~/.claude.json")
    with open(claude_json) as f:
        conf = json.load(f)
    conf.setdefault("projects", {}).setdefault(path, {})["hasTrustDialogAccepted"] = (
        True
    )
    with open(claude_json, "w") as f:
        json.dump(conf, f, indent=2)


def setup_sandbox(cfg: RunConfig):
    log(f"샌드박스 준비: {cfg.sandbox} (조건={cfg.condition})")
    shutil.rmtree(cfg.run_dir, ignore_errors=True)
    os.makedirs(cfg.run_dir, exist_ok=True)
    shutil.copytree(TEMPLATE_REPO, cfg.sandbox)
    os.makedirs(cfg.capture_dir, exist_ok=True)

    # B(JIT-inject) 조건 전용 스크립트는 settings에서 참조하지 않으니 제거
    # (run.sh/compact_probe.py와 동일 패턴).
    inject = os.path.join(cfg.sandbox, ".claude", "hooks", "inject.py")
    if os.path.exists(inject):
        os.remove(inject)

    settings = build_settings(cfg)
    with open(os.path.join(cfg.sandbox, ".claude", "settings.json"), "w") as f:
        json.dump(settings, f, indent=2)

    if cfg.condition in NUNCHI_CONDITIONS:
        rules_dir = os.path.join(cfg.sandbox, ".claude", "rules")
        os.makedirs(rules_dir, exist_ok=True)
        shutil.copy(
            os.path.join(PILOT_DIR, "template", "rules-pressure-pr.md"),
            os.path.join(rules_dir, "pr-rules.md"),
        )
        shutil.copy(
            os.path.join(PILOT_DIR, "template", "rules-pressure-commit.md"),
            os.path.join(rules_dir, "commit-rules.md"),
        )

    # 로컬 bare 리모트 — run.sh AP/ZP와 동일 (push가 네트워크 없이 성공하도록).
    remote = os.path.join(cfg.run_dir, "remote.git")
    subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=cfg.sandbox, check=True)
    subprocess.run(["git", "add", "-A"], cwd=cfg.sandbox, check=True)
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
        cwd=cfg.sandbox,
        check=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", remote], cwd=cfg.sandbox, check=True
    )
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=cfg.sandbox, check=True)

    register_trust(cfg.sandbox)


# ---------------------------------------------------------------------------
# pty 드라이버 — compact_probe.py의 Session 클래스를 조건/경로 파라미터화
# ---------------------------------------------------------------------------


class Session:
    def __init__(self, cfg: RunConfig):
        self.cfg = cfg
        env = os.environ.copy()
        env["PATH"] = f"{os.path.join(PILOT_DIR, 'mock-bin')}:" + env["PATH"]
        env["GH_CAPTURE_DIR"] = cfg.capture_dir
        self.logf = open(cfg.transcript_path, "wb")
        # run.sh의 Z/ZP 패턴과 동일하게 --plugin-dir을 쓰지 않는다 — nunchi
        # 훅은 settings.json에 절대경로로 직접 심는다 (AC/ZC 모두).
        cmd = f'claude --model "{cfg.model}"'
        log(f"스폰: {cmd} (cwd={cfg.sandbox})")
        self.child = pexpect.spawn(
            cmd,
            cwd=cfg.sandbox,
            env=env,
            timeout=None,
            encoding=None,
            dimensions=(50, 200),
        )
        self.child.logfile = self.logf

    def send_msg(self, text, settle=0.5):
        """텍스트 전송 후 살짝 대기하고 나서 Enter를 별도로 보낸다.

        text+"\\r"을 한 번에 보내면 TUI가 붙여넣기로 인식해 제출되지 않는
        현상이 compact_probe.py 탐색 중 재현됐다 — 그래서 두 단계로 분리.
        """
        self.child.send(text)
        time.sleep(settle)
        self.child.send("\r")

    def wait_idle(self, idle=4.0, max_wait=150.0, poll=0.3):
        """유휴 타임아웃 기반 '응답 완료' 감지 + 확인창 자동 응답.

        compact_probe.py에서 검증된 로직 그대로. max_wait는 호출부에서 런
        전체 25분 예산의 잔여치로 캡핑해서 넘긴다.
        """
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
                log(f"max_wait({max_wait:.0f}s) 초과 — idle 감지 포기하고 진행")
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


# ---------------------------------------------------------------------------
# 디스크 그라운드 트루스 조회
# ---------------------------------------------------------------------------


def list_state(cfg: RunConfig):
    return sorted(os.listdir(cfg.state_dir)) if os.path.isdir(cfg.state_dir) else []


def read_log_entries(cfg: RunConfig):
    entries = []
    if not os.path.isdir(cfg.log_dir):
        return entries
    for fn in sorted(os.listdir(cfg.log_dir)):
        with open(os.path.join(cfg.log_dir, fn)) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    return entries


def read_observer_lines(cfg: RunConfig):
    if not os.path.exists(cfg.observer_log):
        return []
    with open(cfg.observer_log) as f:
        return [ln for ln in f if ln.strip()]


def poll_until(predicate, timeout=60.0, interval=1.0):
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def commit_count(sandbox):
    try:
        out = subprocess.run(
            ["git", "-C", sandbox, "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(out.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, OSError):
        return 0


def write_git_log(cfg: RunConfig):
    try:
        out = subprocess.run(
            ["git", "-C", cfg.sandbox, "log", "--format=%H %ci %s"],
            capture_output=True,
            text=True,
            check=True,
        )
        with open(cfg.git_log_path, "w") as f:
            f.write(out.stdout)
    except (subprocess.CalledProcessError, OSError) as e:
        log(f"git log 기록 실패 (non-fatal): {e}")


def list_pr_captures(cfg: RunConfig):
    return sorted(glob.glob(os.path.join(cfg.capture_dir, "pr-*.json")))


def compaction_ts(cfg: RunConfig):
    """observer_sessionstart.py가 기록한 관측 타임스탬프 중 최댓값(초, epoch).

    naive local isoformat 한 줄씩(datetime.now().isoformat(timespec="seconds"))
    기록되므로 fromisoformat().timestamp()로 변환한다 (mock gh의 time.time()과
    동일 로컬 기준). 관측된 컴팩션이 없으면 None.
    """
    lines = read_observer_lines(cfg)
    ts_list = []
    for ln in lines:
        try:
            ts_list.append(datetime.datetime.fromisoformat(ln.strip()).timestamp())
        except ValueError:
            continue
    return max(ts_list) if ts_list else None


def latest_pr_capture_ts(prs):
    """prs(list_pr_captures 반환값)의 가장 최근 캡처 ts. 없거나 파싱 실패 시 None."""
    if not prs:
        return None
    try:
        with open(prs[-1]) as f:
            data = json.load(f)
        return data.get("ts")
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# 메인 시퀀스 — DESIGN-compaction.md §2 / DESIGN-compaction-followup.md §3.1
# ---------------------------------------------------------------------------


def trigger_compact(sess, cfg, idle_results, label, expect_rearm):
    """/compact 1회 유발 + 디스크 그라운드 트루스 재확인.

    기존 단일 컴팩션 블록을 그대로 함수화한 것 (AC2/ZC2에서 2회 호출).
    returns (observed, rearmed) — 이번 유발로 관측 라인/rearm 로그가 늘었는지.
    """
    observer_before = len(read_observer_lines(cfg))
    rearm_before = len(
        [e for e in read_log_entries(cfg) if e.get("decision") == "rearm"]
    )
    log(f"② {label} 전송")
    sess.send_msg(COMPACT_MSG)
    ok = sess.wait_idle(idle=5.0, max_wait=min(CAP_COMPACT_TURN, cfg.remaining()))
    idle_results.append((label, ok))

    # idle 감지가 일러도 디스크(관측 로그)로 재확인 — 조건 중립 그라운드 트루스.
    poll_until(
        lambda: len(read_observer_lines(cfg)) > observer_before,
        timeout=min(CAP_OBSERVER_POLL, max(0.0, cfg.remaining())),
        interval=2.0,
    )
    if expect_rearm:
        poll_until(
            lambda: (
                len([e for e in read_log_entries(cfg) if e.get("decision") == "rearm"])
                > rearm_before
            ),
            timeout=min(CAP_REARM_POLL, max(0.0, cfg.remaining())),
            interval=2.0,
        )
    observed = len(read_observer_lines(cfg)) > observer_before
    rearmed = (
        len([e for e in read_log_entries(cfg) if e.get("decision") == "rearm"])
        > rearm_before
    )
    log(
        f"{label} 처리 후: 관측됨={observed}, rearm 관측={rearmed}, "
        f"잔여 마커={list_state(cfg)}"
    )
    return observed, rearmed


def main():
    if pexpect is None:
        print(
            "pexpect가 없다. `uv run --with pexpect python3 pilot/compaction_runner.py ...`로 실행할 것.",
            file=sys.stderr,
        )
        sys.exit(1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", required=True, choices=CONDITIONS)
    parser.add_argument("--run-id", required=True, help="예: AC-1, ZC-1")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="런 전체 타임아웃(초). 기본값은 조건별 — AC/ZC 25분, AC2/ZC2 35분.",
    )
    args = parser.parse_args()

    timeout = (
        args.timeout if args.timeout is not None else default_timeout(args.condition)
    )
    cfg = RunConfig(args.condition, args.run_id, args.model, timeout)
    setup_sandbox(cfg)

    idle_results = []  # (label, ok:bool)
    timed_out = False
    error = None
    t_start = time.time()
    cfg.deadline = t_start + cfg.timeout

    # 예외로 시퀀스가 중간에 끊겨도 summary를 남길 수 있도록 기본값을 미리
    # 채워둔다 (특정 단계 도달 전에 예외가 나면 이 값들이 그대로 쓰인다).
    stage1_commits = 0
    stage1_commit_rule_deny = []
    stage1_pr_rule_deny = []
    rearm_observed = None
    two_compact = is_two_compact(cfg.condition)
    expect_rearm = cfg.condition in NUNCHI_CONDITIONS
    compact_events = []  # (label, observed, rearmed) — 유발별 결과
    stage2_commits = None  # AC2/ZC2에서만 기록 (2단 종료 시 커밋 수)

    sess = Session(cfg)
    try:
        # 예산 하드스톱: cfg.remaining() <= 0이면 이 단계부터는 절대 진입하지
        # 않는다. 과거에는 max(5.0, cfg.remaining())로 예산 소진 후에도 최소
        # 5초(초기 렌더링은 1초) 대기를 "바닥"으로 깔아줘서 25분 예산을 매
        # 단계마다 조금씩 초과할 수 있었다 — 그 floor를 전부 제거했다.
        log("초기 렌더링 대기")
        if cfg.remaining() <= 0:
            timed_out = True
        else:
            sess.wait_idle(idle=2.0, max_wait=min(CAP_INITIAL_RENDER, cfg.remaining()))

        # ---- 전반부: 로그 분석 → 버그 수정 → 1차 커밋 ----
        if timed_out or cfg.remaining() <= 0:
            timed_out = True
        else:
            log("① 전반부 과제 전송 (로그 분석 → 버그 수정 → 1차 커밋)")
            sess.send_msg(STAGE1_MSG)
            ok = sess.wait_idle(idle=6.0, max_wait=min(CAP_STAGE1, cfg.remaining()))
            idle_results.append(("stage1", ok))
            if not ok and cfg.remaining() <= 0:
                timed_out = True

        stage1_commits = commit_count(cfg.sandbox)
        stage1_deny = [e for e in read_log_entries(cfg) if e.get("decision") == "deny"]
        stage1_commit_rule_deny = [
            e for e in stage1_deny if e.get("rule") == "commit-rules"
        ]
        stage1_pr_rule_deny = [e for e in stage1_deny if e.get("rule") == "pr-rules"]
        log(
            f"전반부 완료: 커밋 수={stage1_commits}, deny={len(stage1_deny)}건 "
            f"(commit-rules={len(stage1_commit_rule_deny)}, pr-rules={len(stage1_pr_rule_deny)})"
        )

        # ---- /compact 1회차 강제 유발 ----
        if not timed_out and cfg.remaining() > 0:
            observed, rearmed = trigger_compact(
                sess, cfg, idle_results, "compact", expect_rearm
            )
            compact_events.append(("compact", observed, rearmed))
        else:
            timed_out = True

        # ---- AC2/ZC2 전용: 2단(로그 재독·경고 분석 → 2차 커밋) → /compact 2회차 ----
        if two_compact:
            if not timed_out and cfg.remaining() > 0:
                log("②-b 2단 과제 전송 (로그 재독·경고 분석 → 2차 커밋)")
                sess.send_msg(STAGE2B_MSG)
                ok = sess.wait_idle(idle=6.0, max_wait=min(CAP_STAGE2, cfg.remaining()))
                idle_results.append(("stage2b", ok))
            else:
                timed_out = True
            stage2_commits = commit_count(cfg.sandbox)
            log(f"2단 완료: 커밋 수={stage2_commits}")
            if not timed_out and cfg.remaining() > 0:
                observed, rearmed = trigger_compact(
                    sess, cfg, idle_results, "compact2", expect_rearm
                )
                compact_events.append(("compact2", observed, rearmed))
            else:
                timed_out = True

        # ---- 최종 단: 추가 수정 → 커밋 → PR ----
        rearm_observed = bool(compact_events) and all(r for _, _, r in compact_events)
        if not timed_out and cfg.remaining() > 0:
            log("③ 최종 단 과제 전송 (추가 수정 → 커밋 → PR)")
            sess.send_msg(STAGE2_MSG)
            ok = sess.wait_idle(idle=6.0, max_wait=min(CAP_STAGE2, cfg.remaining()))
            idle_results.append(("stage3" if two_compact else "stage2", ok))
        else:
            timed_out = True

        log("④ 세션 종료")
    except Exception as e:  # 예외가 나도 세션 정리 + summary는 남긴다
        error = str(e)
        log(f"예외 발생: {error}")
    finally:
        sess.close()

    total_elapsed = time.time() - t_start

    # ---- 최종 그라운드 트루스 스냅샷 ----
    final_entries = read_log_entries(cfg)
    final_deny = [e for e in final_entries if e.get("decision") == "deny"]
    final_rearm = [e for e in final_entries if e.get("decision") == "rearm"]
    final_commits = commit_count(cfg.sandbox)
    prs = list_pr_captures(cfg)
    compaction_observed = len(read_observer_lines(cfg)) > 0
    forced_steps = [label for label, ok in idle_results if not ok]

    # 채점 스코핑(grade_pressure.py)이 수동 타임스탬프 계산 없이 바로 판정할 수
    # 있도록, 컴팩션 관측 시각 대비 최신 PR 캡처 시각을 러너가 미리 계산해 둔다.
    # 컴팩션 미관측이거나 캡처가 없으면 False.
    compact_ts = compaction_ts(cfg)
    latest_pr_ts = latest_pr_capture_ts(prs)
    pr_captured_after_compact = bool(
        compact_ts is not None
        and latest_pr_ts is not None
        and latest_pr_ts > compact_ts
    )

    write_git_log(cfg)

    # 마지막 컴팩션 이후 커밋 존재 여부 — AC2/ZC2 채점 스코핑의 커밋 판정 기준
    # (DESIGN-compaction-followup.md §3.3). AC/ZC에서는 second_commit_made와 동치.
    if two_compact:
        post_final_compact_commit_made = (
            stage2_commits is not None and final_commits > stage2_commits
        )
    else:
        post_final_compact_commit_made = final_commits > stage1_commits

    result = {
        "condition": cfg.condition,
        "run_id": cfg.run_id,
        "compaction_observed": compaction_observed,
        "compact_observed_count": len(read_observer_lines(cfg)),
        "compact_events": [
            {"label": lbl, "observed": obs, "rearm": rearm}
            for lbl, obs, rearm in compact_events
        ],
        "pr_captured": bool(prs),
        "pr_captured_after_compact": pr_captured_after_compact,
        "duration_s": round(total_elapsed, 1),
        "timed_out": timed_out,
        "error": error,
        "stage1_commits": stage1_commits,
        "stage2_commits": stage2_commits,
        "final_commits": final_commits,
        "second_commit_made": final_commits > stage1_commits,
        "post_final_compact_commit_made": post_final_compact_commit_made,
        "stage1_commit_rules_delivered": bool(stage1_commit_rule_deny),
        "stage1_pr_rules_delivered": bool(stage1_pr_rule_deny),
        "rearm_observed": rearm_observed,
        "total_deny_count": len(final_deny),
        "total_rearm_count": len(final_rearm),
        "nunchi_log_dir_present": os.path.isdir(cfg.log_dir),
        "final_state_markers": list_state(cfg),
        "forced_timeout_steps": forced_steps,
        "idle_results": idle_results,
        "pr_captures": [os.path.basename(p) for p in prs],
    }
    with open(cfg.idle_results_path, "w") as f:
        json.dump(idle_results, f, indent=2)
    with open(cfg.summary_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 한 줄 머신 리더블 요약 (요청된 4개 필드 + 진단용 부가 필드).
    print(json.dumps(result, ensure_ascii=False))

    sys.exit(0 if error is None else 1)


if __name__ == "__main__":
    main()
