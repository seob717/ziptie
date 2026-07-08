"""ziptie 배달 엔진 — 매칭, 강도 결정, 세션 상태, 로깅."""
import datetime
import json
import os
import re
import sys

from core.rules import Rule, load_rules

REQUIRE_READ_TEMPLATE = (
    "[ziptie:{name}] 이 작업 전에 확인할 규칙이 있어. 아래 규칙을 빠짐없이 반영한 뒤 "
    "같은 작업을 다시 시도해 (재시도는 통과된다).\n\n{content}"
)
BLOCK_TEMPLATE = (
    "[ziptie:{name}] 이 작업은 규칙에 의해 차단됐어. 아래 규칙을 읽고 허용된 대안으로 "
    "진행해.\n\n{content}"
)


def _match_field(rule: Rule, tool_name: str, tool_input: dict):
    if rule.tool != tool_name:
        return None
    if tool_name == "Bash":
        return tool_input.get("command", "")
    return tool_input.get("file_path", "")  # Edit/Write/기타: 경로 매칭 (MVP)


def _content(rule: Rule, project_dir: str) -> str:
    if rule.source:
        try:
            with open(os.path.join(project_dir, rule.source), encoding="utf-8") as f:
                return f.read()  # 배달 시점에 원본을 읽는다 — 복붙 아님
        except OSError:
            pass
    return rule.body


def _log(project_dir: str, session: str, rule: Rule, tool: str, decision: str):
    try:
        log_dir = os.path.join(project_dir, ".claude", "ziptie", "logs")
        os.makedirs(log_dir, exist_ok=True)
        entry = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "session": session, "rule": rule.name, "tool": tool, "decision": decision,
        }
        with open(os.path.join(log_dir, f"{datetime.date.today()}.jsonl"), "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"ziptie: log write failed: {e}", file=sys.stderr)


def _deny(rule: Rule, content: str) -> dict:
    template = BLOCK_TEMPLATE if rule.strength == "block" else REQUIRE_READ_TEMPLATE
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": template.format(name=rule.name, content=content),
        }
    }


def decide(input_data: dict, project_dir: str) -> dict:
    """훅 입력 → 응답. 어떤 예외도 밖으로 내지 않는다 (실패 시 allow)."""
    try:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {}) or {}
        session = input_data.get("session_id", "nosession")
        for rule in load_rules(project_dir):
            field = _match_field(rule, tool_name, tool_input)
            if field is None:
                continue
            try:
                matched = re.search(rule.pattern, field)
            except re.error as e:
                print(f"ziptie: rule {rule.name} match error: {e}", file=sys.stderr)
                continue
            if not matched:
                continue
            if rule.strength == "require-read":
                state_dir = os.path.join(project_dir, ".claude", "ziptie", "state")
                os.makedirs(state_dir, exist_ok=True)
                marker = os.path.join(state_dir, f"{session}--{rule.name}")
                if os.path.exists(marker):
                    _log(project_dir, session, rule, tool_name, "allow-after-delivery")
                    continue
                with open(marker, "w") as f:
                    f.write("delivered")
            _log(project_dir, session, rule, tool_name, "deny")
            return _deny(rule, _content(rule, project_dir))
        return {}
    except Exception as e:  # 안전 기본값
        print(f"ziptie: engine error: {e}", file=sys.stderr)
        return {}
