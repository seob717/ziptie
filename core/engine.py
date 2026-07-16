"""nunchi 배달 엔진 — 매칭, 강도 결정, 세션 상태, 로깅."""

import contextlib
import datetime
import io
import json
import os
import re
import sys
from typing import List

from core.rules import Rule, load_rules

_SESSION_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize_session(session_id: str) -> str:
    """마커 파일명에 쓰기 전에 세션 id를 정화한다.

    경로 구분자 등 [A-Za-z0-9._-] 밖의 문자는 전부 "-"로 치환 —
    open()이 세션 문자열 때문에 실패해 룰 평가(특히 block 룰)를 통째로
    무산시키는 일이 없도록 한다.
    """
    return _SESSION_SAFE_RE.sub("-", session_id or "nosession")


REQUIRE_READ_TEMPLATE = (
    "[nunchi:{name}] There are rules to check before this action. Apply every rule "
    "below, then retry the same action (the retry will pass).\n\n{content}"
)
BLOCK_TEMPLATE = (
    "[nunchi:{name}] This action is blocked by a rule. Read the rule below and "
    "proceed with an allowed alternative.\n\n{content}"
)
# 신뢰 프레이밍이 준수를 가른다 (PROBE-inject.md 판정 ③) — 출처 없는 주입은
# 모델이 프롬프트 인젝션으로 취급해 거부하므로, 프로젝트 소유자 설정·등록
# 위치·source 경로를 명시한다.
INJECT_TEMPLATE = (
    "[nunchi:{name}] Rule delivery from this project's .claude/rules/ "
    "(a nunchi hook configured by the project owner delivers the rules matching "
    "this tool call{source_note}). Rules that apply to this action:\n\n{content}"
)
# 재컴파일 신호 (#17): 내용 보강은 배달이 원본을 매번 읽어 자동 반영되지만,
# 규칙 신설·트리거 재바인딩·강도 변경은 재컴파일 없이는 영영 반영되지 않는다
# — source 문서 편집 시점이 그걸 알릴 유일한 무음 아닌 순간이다.
RECOMPILE_TEMPLATE = (
    "[nunchi:recompile] The file being modified is the source document of the "
    "compiled rule(s) {names} (delivered just-in-time by this project's nunchi "
    "hook). Content-only refinements need no follow-up — deliveries read this "
    "document fresh every time. But if this change adds a rule for a new "
    "action, rebinds a rule to a different action, or changes a prohibition's "
    "strength, the compiled triggers go stale: after the edit, run "
    "`/nunchi:compile {source}` or suggest it to the user."
)


def _match_field(rule: Rule, tool_name: str, tool_input: dict):
    if rule.tool != tool_name:
        return None
    if rule.field:
        value = tool_input.get(rule.field)
        # 필드 부재·비문자열(중첩 구조 등)은 매칭 불가로 취급
        return value if isinstance(value, str) else None
    if tool_name == "Bash":
        return tool_input.get("command", "")
    return tool_input.get("file_path", "")  # Edit/Write/기타: 경로 매칭 (기본)


def _content(rule: Rule, project_dir: str) -> str:
    if rule.source:
        try:
            with open(os.path.join(project_dir, rule.source), encoding="utf-8") as f:
                return f.read()  # 배달 시점에 원본을 읽는다 — 복붙 아님
        except Exception:
            pass  # 파일 없음·권한·인코딩 깨짐 등 — 룰 본문으로 폴백 (배치 전체를 죽이지 않음)
    return rule.body


def _log(
    project_dir: str, session: str, rule_name: str, tool: str, decision: str, extra=None
):
    try:
        log_dir = os.path.join(project_dir, ".claude", "nunchi", "logs")
        os.makedirs(log_dir, exist_ok=True)
        entry = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "session": session,
            "rule": rule_name,
            "tool": tool,
            "decision": decision,
        }
        if extra:
            entry.update(extra)
        with open(os.path.join(log_dir, f"{datetime.date.today()}.jsonl"), "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"nunchi: log write failed: {e}", file=sys.stderr)


def _recompile_notice(
    rules: List[Rule], tool_name: str, tool_input: dict, project_dir: str
):
    """Edit/Write 대상이 컴파일된 룰의 source 문서면 재컴파일 안내를 만든다.

    반환: (안내문, source 경로) 또는 None. 세션 마커 확인·기록은 호출부 몫.
    이미 로드된 룰 목록만 훑으므로 무매칭 호출에 추가 비용이 없다.
    """
    if tool_name not in ("Edit", "Write"):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    # join은 절대경로 file_path를 그대로 통과시킨다 — 상대·절대 모두 처리
    target = os.path.realpath(os.path.join(project_dir, file_path))
    hit = [
        r
        for r in rules
        if r.source and os.path.realpath(os.path.join(project_dir, r.source)) == target
    ]
    if not hit:
        return None
    names = ", ".join(sorted({r.name for r in hit}))
    source = hit[0].source
    return RECOMPILE_TEMPLATE.format(names=names, source=source), source


def _reason(rule: Rule, content: str) -> str:
    if rule.strength == "block":
        return BLOCK_TEMPLATE.format(name=rule.name, content=content)
    if rule.strength == "inject":
        source_note = f". source: {rule.source}" if rule.source else ""
        return INJECT_TEMPLATE.format(
            name=rule.name, content=content, source_note=source_note
        )
    return REQUIRE_READ_TEMPLATE.format(name=rule.name, content=content)


def _deny(reasons: List[str]) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "\n\n---\n\n".join(reasons),
        }
    }


def _inject(reasons: List[str]) -> dict:
    """additionalContext 단독 반환 — permissionDecision을 넣지 않는다.

    allow를 반환하면 이 도구 호출이 권한 시스템을 우회한다(규칙 매칭 =
    자동 승인이라는 보안 퇴행). additionalContext만으로 주입이 동작함을
    실측 확인했다 (PROBE-inject.md 판정 ②).
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": "\n\n---\n\n".join(reasons),
        }
    }


def decide(input_data: dict, project_dir: str) -> dict:
    """훅 입력 → 응답. 어떤 예외도 밖으로 내지 않는다 (실패 시 allow)."""
    try:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {}) or {}
        session = _sanitize_session(input_data.get("session_id", "nosession"))
        state_dir = os.path.join(project_dir, ".claude", "nunchi", "state")
        warned_marker = os.path.join(state_dir, f"warned--{session}")
        # 마커 존재 확인은 non-fatal — 실패하면 quiet=False로 취급 (경고를 못 억제할
        # 뿐, block 룰 평가는 아래 어떤 state-dir 부작용에도 의존하지 않는다).
        try:
            quiet = os.path.exists(warned_marker)
        except OSError:
            quiet = False

        to_deliver = []
        warnings_buf = io.StringIO()
        with contextlib.redirect_stderr(warnings_buf):
            rules = load_rules(project_dir, quiet=quiet)
            for rule in rules:
                field = _match_field(rule, tool_name, tool_input)
                if field is None:
                    continue
                try:
                    matched = re.search(rule.pattern, field)
                    if matched and rule.path_pattern:
                        # path AND 조건 — content 룰이 문서·마크다운 속 예시
                        # 코드에 걸리는 오탐 방지. file_path 부재는 매칭 불가.
                        path = tool_input.get("file_path")
                        matched = isinstance(path, str) and re.search(
                            rule.path_pattern, path
                        )
                except re.error as e:
                    if not quiet:
                        print(
                            f"nunchi: rule {rule.name} match error: {e}",
                            file=sys.stderr,
                        )
                    continue
                if not matched:
                    continue
                if rule.strength in ("require-read", "inject"):
                    marker = os.path.join(state_dir, f"{session}--{rule.name}")
                    if os.path.exists(marker):
                        _log(
                            project_dir,
                            session,
                            rule.name,
                            tool_name,
                            "allow-after-delivery",
                        )
                        continue
                to_deliver.append(rule)

        warnings_text = warnings_buf.getvalue()
        if warnings_text:
            sys.stderr.write(warnings_text)
            if not quiet:
                # 마커 기록은 "경고가 실제로 있었을 때만" 시도한다 — 무경고 호출마다
                # state-dir에 파일을 남기던 부작용 제거. 기록 실패도 non-fatal.
                try:
                    os.makedirs(state_dir, exist_ok=True)
                    with open(warned_marker, "w") as f:
                        f.write("warned")
                except OSError:
                    pass

        # 재컴파일 신호 (#17): 편집 대상이 어떤 룰의 source 문서면 세션당
        # 1회 안내한다. 마커는 "{session}--" 접두라 rearm이 함께 리셋한다.
        recompile = _recompile_notice(rules, tool_name, tool_input, project_dir)
        if recompile:
            recompile_marker = os.path.join(
                state_dir,
                f"{session}--recompile--{_SESSION_SAFE_RE.sub('-', recompile[1])}",
            )
            if os.path.exists(recompile_marker):
                recompile = None

        if not to_deliver and not recompile:
            return {}

        # 콘텐츠 조립을 마커 기록보다 먼저 수행한다 — 한 룰의 배달 실패가
        # 이미 조립된 다른 룰의 마커 기록(=배달 확정)을 소급 무효화하지 않도록.
        reasons = [_reason(rule, _content(rule, project_dir)) for rule in to_deliver]
        if recompile:
            reasons.append(recompile[0])

        # inject 룰만 매칭됐으면(재컴파일 안내 단독 포함) 차단 없이 주입한다.
        # deny가 어차피 발생하는 호출이면 inject 내용도 그 사유에 병합 배달한다
        # — 한 번의 재시도로 전부 커버 (병합 배달 철학 유지).
        inject_only = all(rule.strength == "inject" for rule in to_deliver)
        decision = "inject" if inject_only else "deny"

        for rule in to_deliver:
            if rule.strength in ("require-read", "inject"):
                os.makedirs(state_dir, exist_ok=True)
                marker = os.path.join(state_dir, f"{session}--{rule.name}")
                with open(marker, "w") as f:
                    f.write("delivered")
            _log(project_dir, session, rule.name, tool_name, decision)

        if recompile:
            # 마커 기록 실패는 룰 배달(이미 확정)을 소급 무효화하면 안 된다
            # — 억제하고 배달은 그대로 나간다 (최악은 안내 재배달).
            with contextlib.suppress(OSError):
                os.makedirs(state_dir, exist_ok=True)
                with open(recompile_marker, "w") as f:
                    f.write("delivered")
            _log(
                project_dir,
                session,
                "(recompile)",
                tool_name,
                decision,
                extra={"source": recompile[1]},
            )

        return _inject(reasons) if inject_only else _deny(reasons)
    except Exception as e:  # 안전 기본값
        print(f"nunchi: engine error: {e}", file=sys.stderr)
        return {}


def record_session(input_data, project_dir: str) -> None:
    """세션을 1회 관측 기록한다 — InstructionsLoaded 훅 엔트리에서 호출.

    배달 로그만으로는 무배달 세션이 보이지 않아 누적 절약(세션수×고정비)이
    과소 계상된다(#10). 세션당 정확히 1줄만 남긴다: seen-- 마커가 있으면
    무시. 마커는 "{session}--" 접두사가 아니므로 rearm에서 살아남는다 —
    컴팩션 후 재발화해도 같은 세션을 중복 계상하지 않는다.
    """
    try:
        input_data = input_data or {}
        session = _sanitize_session(input_data.get("session_id", "nosession"))
        state_dir = os.path.join(project_dir, ".claude", "nunchi", "state")
        marker = os.path.join(state_dir, f"seen--{session}")
        if os.path.exists(marker):
            return
        os.makedirs(state_dir, exist_ok=True)
        with open(marker, "w") as f:
            f.write("seen")
        _log(project_dir, session, "(session)", "InstructionsLoaded", "session-start")
    except Exception as e:
        print(f"nunchi: record_session error: {e}", file=sys.stderr)


def rearm(input_data, project_dir: str) -> None:
    """컴팩션 직후 세션의 배달 마커를 리셋한다 — 룰이 JIT로 재배달되게.

    warned-- 마커는 유지(경고 억제는 컴팩션과 무관). 어떤 예외도 밖으로
    내지 않으며, stdout에는 아무것도 쓰지 않는다.
    """
    try:
        input_data = input_data or {}
        session = _sanitize_session(input_data.get("session_id", "nosession"))
        state_dir = os.path.join(project_dir, ".claude", "nunchi", "state")
        if not os.path.isdir(state_dir):
            return  # 배달된 적 없는 프로젝트 — 리셋할 마커도 없다 (stderr 노이즈 방지)
        prefix = f"{session}--"
        warned_marker = f"warned--{session}"
        removed = 0
        for fn in os.listdir(state_dir):
            if fn.startswith(prefix) and fn != warned_marker:
                with contextlib.suppress(OSError):
                    os.remove(os.path.join(state_dir, fn))
                    removed += 1
        if removed:
            _log(
                project_dir,
                session,
                "(compact)",
                "SessionStart",
                "rearm",
                extra={"count": removed},
            )
    except Exception as e:
        print(f"nunchi: rearm error: {e}", file=sys.stderr)
