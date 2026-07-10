"""ziptie 배달 엔진 — 매칭, 강도 결정, 세션 상태, 로깅."""

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
    "[ziptie:{name}] 이 작업 전에 확인할 규칙이 있어. 아래 규칙을 빠짐없이 반영한 뒤 "
    "같은 작업을 다시 시도해 (재시도는 통과된다).\n\n{content}"
)
BLOCK_TEMPLATE = (
    "[ziptie:{name}] 이 작업은 규칙에 의해 차단됐어. 아래 규칙을 읽고 허용된 대안으로 "
    "진행해.\n\n{content}"
)
# 신뢰 프레이밍이 준수를 가른다 (PROBE-inject.md 판정 ③) — 출처 없는 주입은
# 모델이 프롬프트 인젝션으로 취급해 거부하므로, 프로젝트 소유자 설정·등록
# 위치·source 경로를 명시한다.
INJECT_TEMPLATE = (
    "[ziptie:{name}] 이 프로젝트의 .claude/rules/에 등록된 규칙 배달입니다 "
    "(프로젝트 소유자가 설정한 ziptie 훅이 이 도구 호출에 매칭되는 규칙을 "
    "배달합니다{source_note}). 이 작업에 적용되는 규칙:\n\n{content}"
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
        log_dir = os.path.join(project_dir, ".claude", "ziptie", "logs")
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
        print(f"ziptie: log write failed: {e}", file=sys.stderr)


def _reason(rule: Rule, content: str) -> str:
    if rule.strength == "block":
        return BLOCK_TEMPLATE.format(name=rule.name, content=content)
    if rule.strength == "inject":
        source_note = f". source: {rule.source}" if rule.source else ""
        return INJECT_TEMPLATE.format(
            name=rule.name, content=content, source_note=source_note
        )
    return REQUIRE_READ_TEMPLATE.format(name=rule.name, content=content)


def _deny(deliveries: List[tuple]) -> dict:
    reason = "\n\n---\n\n".join(_reason(rule, content) for rule, content in deliveries)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _inject(deliveries: List[tuple]) -> dict:
    """additionalContext 단독 반환 — permissionDecision을 넣지 않는다.

    allow를 반환하면 이 도구 호출이 권한 시스템을 우회한다(규칙 매칭 =
    자동 승인이라는 보안 퇴행). additionalContext만으로 주입이 동작함을
    실측 확인했다 (PROBE-inject.md 판정 ②).
    """
    context = "\n\n---\n\n".join(_reason(rule, content) for rule, content in deliveries)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    }


def decide(input_data: dict, project_dir: str) -> dict:
    """훅 입력 → 응답. 어떤 예외도 밖으로 내지 않는다 (실패 시 allow)."""
    try:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {}) or {}
        session = _sanitize_session(input_data.get("session_id", "nosession"))
        state_dir = os.path.join(project_dir, ".claude", "ziptie", "state")
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
            for rule in load_rules(project_dir, quiet=quiet):
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
                            f"ziptie: rule {rule.name} match error: {e}",
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

        if not to_deliver:
            return {}

        # 콘텐츠 조립을 마커 기록보다 먼저 수행한다 — 한 룰의 배달 실패가
        # 이미 조립된 다른 룰의 마커 기록(=배달 확정)을 소급 무효화하지 않도록.
        deliveries = [(rule, _content(rule, project_dir)) for rule in to_deliver]

        # inject 룰만 매칭됐으면 차단 없이 주입한다. deny가 어차피 발생하는
        # 호출이면 inject 내용도 그 사유에 병합 배달한다 — 한 번의 재시도로
        # 전부 커버 (병합 배달 철학 유지).
        inject_only = all(rule.strength == "inject" for rule in to_deliver)
        decision = "inject" if inject_only else "deny"

        for rule in to_deliver:
            if rule.strength in ("require-read", "inject"):
                os.makedirs(state_dir, exist_ok=True)
                marker = os.path.join(state_dir, f"{session}--{rule.name}")
                with open(marker, "w") as f:
                    f.write("delivered")
            _log(project_dir, session, rule.name, tool_name, decision)

        return _inject(deliveries) if inject_only else _deny(deliveries)
    except Exception as e:  # 안전 기본값
        print(f"ziptie: engine error: {e}", file=sys.stderr)
        return {}


def rearm(input_data, project_dir: str) -> None:
    """컴팩션 직후 세션의 배달 마커를 리셋한다 — 룰이 JIT로 재배달되게.

    warned-- 마커는 유지(경고 억제는 컴팩션과 무관). 어떤 예외도 밖으로
    내지 않으며, stdout에는 아무것도 쓰지 않는다.
    """
    try:
        input_data = input_data or {}
        session = _sanitize_session(input_data.get("session_id", "nosession"))
        state_dir = os.path.join(project_dir, ".claude", "ziptie", "state")
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
        print(f"ziptie: rearm error: {e}", file=sys.stderr)
