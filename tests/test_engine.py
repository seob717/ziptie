import glob
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import engine
from core.engine import decide

RULE = """---
name: pr-rules
trigger:
  tool: Bash
  pattern: gh\\s+pr\\s+create
source: docs/pr-rules.md
strength: require-read
---
요약: PR 규칙을 따르라.
"""


def make_project(rule_text=RULE, with_source=True):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, ".claude", "rules"))
    with open(os.path.join(d, ".claude", "rules", "pr.md"), "w") as f:
        f.write(rule_text)
    if with_source:
        os.makedirs(os.path.join(d, "docs"))
        with open(os.path.join(d, "docs", "pr-rules.md"), "w") as f:
            f.write("# PR 규칙\n1. 제목은 [LAB-123] 형식")
    return d


def hook_input(command="gh pr create --title x", session="s1", tool="Bash"):
    return {
        "hook_event_name": "PreToolUse",
        "session_id": session,
        "tool_name": tool,
        "tool_input": {"command": command},
    }


def test_first_match_denies_with_source_content():
    d = make_project()
    out = decide(hook_input(), d)
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert "[LAB-123]" in hso["permissionDecisionReason"]  # 원본 문서가 배달됨
    assert "ziptie" in hso["permissionDecisionReason"]


def test_second_call_same_session_allows():
    d = make_project()
    decide(hook_input(session="s2"), d)
    assert decide(hook_input(session="s2"), d) == {}


def test_different_session_denies_again():
    d = make_project()
    decide(hook_input(session="s3"), d)
    assert (
        decide(hook_input(session="s4"), d)["hookSpecificOutput"]["permissionDecision"]
        == "deny"
    )


def test_no_match_allows():
    d = make_project()
    assert decide(hook_input(command="git status"), d) == {}
    assert decide(hook_input(tool="Read"), d) == {}


def test_block_strength_always_denies():
    d = make_project(RULE.replace("strength: require-read", "strength: block"))
    decide(hook_input(session="s5"), d)
    out = decide(hook_input(session="s5"), d)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_missing_source_falls_back_to_body():
    d = make_project(with_source=False)
    reason = decide(hook_input(), d)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "PR 규칙을 따르라" in reason


def test_file_tool_matches_on_file_path():
    rule = "---\nname: test-rules\ntrigger:\n  tool: Edit\n  pattern: \\.test\\.\n---\n테스트 규칙 본문"
    d = make_project(rule, with_source=False)
    inp = {
        "hook_event_name": "PreToolUse",
        "session_id": "s6",
        "tool_name": "Edit",
        "tool_input": {"file_path": "src/a.test.ts", "new_string": "x"},
    }
    assert decide(inp, d)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_logs_written():
    d = make_project()
    decide(hook_input(session="s7"), d)
    logs = glob.glob(os.path.join(d, ".claude", "ziptie", "logs", "*.jsonl"))
    assert logs
    entry = json.loads(open(logs[0]).readline())
    assert entry["rule"] == "pr-rules" and entry["decision"] == "deny"


def test_engine_never_raises_on_garbage_input():
    d = make_project()
    assert decide({}, d) == {}
    assert decide({"tool_name": "Bash"}, d) == {}


def test_multiple_require_read_rules_merge_in_single_deny():
    d = make_project()
    rule2 = RULE.replace("name: pr-rules", "name: pr-rules-2").replace(
        "docs/pr-rules.md", "docs/pr-rules-2.md"
    )
    with open(os.path.join(d, ".claude", "rules", "pr2.md"), "w") as f:
        f.write(rule2)
    with open(os.path.join(d, "docs", "pr-rules-2.md"), "w") as f:
        f.write("# PR 규칙2\n2. 두번째 규칙 내용")

    out = decide(hook_input(session="s10"), d)
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    reason = hso["permissionDecisionReason"]
    assert "[LAB-123]" in reason
    assert "두번째 규칙 내용" in reason
    assert "pr-rules" in reason and "pr-rules-2" in reason
    assert "\n\n---\n\n" in reason

    state_dir = os.path.join(d, ".claude", "ziptie", "state")
    assert os.path.exists(os.path.join(state_dir, "s10--pr-rules"))
    assert os.path.exists(os.path.join(state_dir, "s10--pr-rules-2"))

    assert decide(hook_input(session="s10"), d) == {}


def test_block_and_require_read_mixed_second_call_denies_with_block_only():
    d = make_project()
    block_rule = RULE.replace("name: pr-rules", "name: pr-block")
    block_rule = block_rule.replace("strength: require-read", "strength: block")
    block_rule = block_rule.replace("docs/pr-rules.md", "docs/pr-block.md")
    with open(os.path.join(d, ".claude", "rules", "pr-block.md"), "w") as f:
        f.write(block_rule)
    with open(os.path.join(d, "docs", "pr-block.md"), "w") as f:
        f.write("# 차단 규칙\n절대 금지")

    first = decide(hook_input(session="s11"), d)
    reason1 = first["hookSpecificOutput"]["permissionDecisionReason"]
    assert "pr-rules" in reason1 and "pr-block" in reason1

    second = decide(hook_input(session="s11"), d)
    assert second["hookSpecificOutput"]["permissionDecision"] == "deny"
    reason2 = second["hookSpecificOutput"]["permissionDecisionReason"]
    assert "pr-block" in reason2
    assert "pr-rules" not in reason2


def test_block_rule_with_malformed_session_id_still_denies():
    d = make_project(RULE.replace("strength: require-read", "strength: block"))
    out = decide(hook_input(session="weird/session"), d)
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"]


def test_require_read_markers_sanitize_session_id_across_calls():
    d = make_project()
    first = decide(hook_input(session="weird/session2"), d)
    assert first["hookSpecificOutput"]["permissionDecision"] == "deny"

    second = decide(hook_input(session="weird/session2"), d)
    assert second == {}

    state_dir = os.path.join(d, ".claude", "ziptie", "state")
    assert os.path.exists(os.path.join(state_dir, "weird-session2--pr-rules"))


def test_bad_encoding_source_does_not_void_batch():
    d = make_project()
    rule2 = RULE.replace("name: pr-rules", "name: pr-rules-2").replace(
        "docs/pr-rules.md", "docs/pr-rules-2.md"
    )
    with open(os.path.join(d, ".claude", "rules", "pr2.md"), "w") as f:
        f.write(rule2)
    with open(os.path.join(d, "docs", "pr-rules-2.md"), "wb") as f:
        f.write(b"\xff\xfe broken content")  # 잘못된 UTF-8

    out = decide(hook_input(session="s30"), d)
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    reason = hso["permissionDecisionReason"]
    assert "[LAB-123]" in reason  # rule1 콘텐츠는 정상 배달
    assert "pr-rules-2" in reason  # rule2도 (폴백이든 스킵이든) 배치에서 사라지지 않음

    state_dir = os.path.join(d, ".claude", "ziptie", "state")
    assert os.path.exists(os.path.join(state_dir, "s30--pr-rules"))

    # 두번째 호출에서 배달되지 않은 룰이 조용히 allow되면 안 된다.
    # rule1은 이미 배달됐으니 allow, rule2가 실제로 배달됐다면 그것도 allow.
    second = decide(hook_input(session="s30"), d)
    assert second == {}


def test_broken_rule_warning_once_per_session(capsys):
    broken = "---\nname: a/b\ntrigger:\n  tool: Bash\n  pattern: foo\n---\nbody"
    d = make_project()
    with open(os.path.join(d, ".claude", "rules", "aa-broken.md"), "w") as f:
        f.write(broken)
    capsys.readouterr()  # 이전 출력 비우기

    decide(hook_input(session="s9"), d)
    first_err = capsys.readouterr().err
    assert "invalid name" in first_err

    decide(hook_input(session="s9"), d)
    second_err = capsys.readouterr().err
    assert second_err == ""

    marker = os.path.join(d, ".claude", "ziptie", "state", "warned--s9")
    assert os.path.exists(marker)


def test_bad_regex_warning_once_per_session(capsys):
    broken = (
        "---\nname: broken-re\ntrigger:\n  tool: Bash\n  pattern: (unbalanced\n---\nb"
    )
    d = make_project()
    with open(os.path.join(d, ".claude", "rules", "aa-broken.md"), "w") as f:
        f.write(broken)  # 정렬상 pr.md보다 먼저 로드되도록 aa- 접두
    capsys.readouterr()  # 이전 출력 비우기

    decide(hook_input(session="s21"), d)
    first_err = capsys.readouterr().err
    assert "match error" in first_err

    decide(hook_input(session="s21"), d)
    second_err = capsys.readouterr().err
    assert second_err == ""


def test_broken_regex_rule_does_not_disable_others():
    broken = (
        "---\nname: broken-re\ntrigger:\n  tool: Bash\n  pattern: (unbalanced\n---\nb"
    )
    d = make_project()
    with open(os.path.join(d, ".claude", "rules", "aa-broken.md"), "w") as f:
        f.write(broken)  # 정렬상 pr.md보다 먼저 로드되도록 aa- 접두
    out = decide(hook_input(session="s8"), d)
    assert (
        out["hookSpecificOutput"]["permissionDecision"] == "deny"
    )  # pr-rules는 여전히 발동


CONTENT_RULE = """---
name: no-console
trigger:
  tool: Edit
  pattern: console\\.log
  field: new_string
strength: require-read
---
console.log 대신 src/logger를 써.
"""


def _edit_input(session, new_string, file_path="src/a.ts"):
    return {
        "hook_event_name": "PreToolUse",
        "session_id": session,
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "new_string": new_string},
    }


def test_content_field_rule_matches_new_string():
    d = make_project(CONTENT_RULE, with_source=False)
    out = decide(_edit_input("f1", 'console.log("x")'), d)
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert "src/logger" in hso["permissionDecisionReason"]


def test_content_field_rule_ignores_non_matching_content():
    d = make_project(CONTENT_RULE, with_source=False)
    assert decide(_edit_input("f2", "logger.info('x')"), d) == {}


def test_content_field_rule_ignores_file_path():
    # field가 지정되면 file_path가 아니라 지정 필드에만 매칭한다.
    d = make_project(CONTENT_RULE, with_source=False)
    assert decide(_edit_input("f3", "clean", file_path="console.log.ts"), d) == {}


def test_content_field_missing_or_non_string_no_match():
    d = make_project(CONTENT_RULE, with_source=False)
    inp = {
        "hook_event_name": "PreToolUse",
        "session_id": "f4",
        "tool_name": "Edit",
        "tool_input": {"file_path": "src/a.ts"},  # new_string 없음
    }
    assert decide(inp, d) == {}
    inp["tool_input"]["new_string"] = ["not", "a", "string"]
    assert decide(inp, d) == {}


PATH_SCOPED_RULE = """---
name: no-any
trigger:
  tool: Edit
  pattern: \\bas\\s+any\\b
  field: new_string
  path: \\.tsx?$
strength: block
---
any 금지.
"""


def test_path_scoped_content_rule_matches_code_file():
    d = make_project(PATH_SCOPED_RULE, with_source=False)
    out = decide(_edit_input("ps1", "const x = y as any", file_path="src/a.ts"), d)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_path_scoped_content_rule_skips_other_paths():
    # 실사용 오탐 사례: 문서 속 예시 코드가 content 패턴에 걸리면 안 된다.
    d = make_project(PATH_SCOPED_RULE, with_source=False)
    inp = _edit_input("ps2", "const x = y as any", file_path="docs/typescript.md")
    assert decide(inp, d) == {}


def test_path_scoped_rule_missing_file_path_no_match():
    d = make_project(PATH_SCOPED_RULE, with_source=False)
    inp = {
        "hook_event_name": "PreToolUse",
        "session_id": "ps3",
        "tool_name": "Edit",
        "tool_input": {"new_string": "y as any"},  # file_path 없음
    }
    assert decide(inp, d) == {}


def test_path_scoped_rule_invalid_path_regex_skipped():
    bad = PATH_SCOPED_RULE.replace("path: \\.tsx?$", "path: \\.tsx?$[")
    d = make_project(bad, with_source=False)
    assert decide(_edit_input("ps4", "y as any", file_path="src/a.ts"), d) == {}


def test_inject_first_match_returns_additional_context_only():
    # PROBE-inject.md 판정 ②: permissionDecision을 넣으면 권한 시스템을
    # 우회하므로 additionalContext 단독으로 반환해야 한다.
    d = make_project(RULE.replace("strength: require-read", "strength: inject"))
    out = decide(hook_input(session="i1"), d)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in hso
    assert "permissionDecisionReason" not in hso
    ctx = hso["additionalContext"]
    assert "[LAB-123]" in ctx  # 원본 문서가 배달됨
    # PROBE-inject.md 판정 ③: 신뢰 프레이밍 필수 — 출처(.claude/rules, source 경로) 명시
    assert "ziptie" in ctx and ".claude/rules" in ctx and "docs/pr-rules.md" in ctx


def test_inject_second_call_same_session_silent():
    d = make_project(RULE.replace("strength: require-read", "strength: inject"))
    decide(hook_input(session="i2"), d)
    assert decide(hook_input(session="i2"), d) == {}


def test_inject_marker_reset_by_rearm_delivers_again():
    d = make_project(RULE.replace("strength: require-read", "strength: inject"))
    decide(hook_input(session="i3"), d)
    assert decide(hook_input(session="i3"), d) == {}
    engine.rearm({"session_id": "i3", "source": "compact"}, d)
    out = decide(hook_input(session="i3"), d)
    assert "additionalContext" in out["hookSpecificOutput"]


def test_inject_logs_inject_decision():
    d = make_project(RULE.replace("strength: require-read", "strength: inject"))
    decide(hook_input(session="i4"), d)
    logs = glob.glob(os.path.join(d, ".claude", "ziptie", "logs", "*.jsonl"))
    entries = [json.loads(ln) for ln in open(logs[0]) if ln.strip()]
    assert any(e["decision"] == "inject" and e["rule"] == "pr-rules" for e in entries)


def test_inject_mixed_with_require_read_merges_into_single_deny():
    # deny가 이미 발생하는 호출이면 inject 내용도 그 사유에 병합 배달한다 —
    # 한 번의 재시도로 전부 커버 (기존 병합 배달 철학 유지).
    d = make_project()
    inject_rule = RULE.replace("name: pr-rules", "name: pr-inject")
    inject_rule = inject_rule.replace("strength: require-read", "strength: inject")
    inject_rule = inject_rule.replace("docs/pr-rules.md", "docs/pr-inject.md")
    with open(os.path.join(d, ".claude", "rules", "pr-inject.md"), "w") as f:
        f.write(inject_rule)
    with open(os.path.join(d, "docs", "pr-inject.md"), "w") as f:
        f.write("# inject 규칙\ninject 전용 내용")

    out = decide(hook_input(session="i5"), d)
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert "inject 전용 내용" in hso["permissionDecisionReason"]

    # 둘 다 배달 확정 — 두번째 호출은 완전 통과
    assert decide(hook_input(session="i5"), d) == {}


class TestRearm(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = os.path.join(self.tmp, ".claude", "ziptie", "state")
        os.makedirs(self.state)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _touch(self, name):
        with open(os.path.join(self.state, name), "w") as f:
            f.write("x")

    def test_rearm_removes_delivery_markers_keeps_warned(self):
        self._touch("sess-1--pr-rules")
        self._touch("sess-1--commit-rules")
        self._touch("warned--sess-1")
        self._touch("sess-2--pr-rules")  # 다른 세션은 건드리지 않음
        engine.rearm({"session_id": "sess-1", "source": "compact"}, self.tmp)
        remaining = sorted(os.listdir(self.state))
        self.assertEqual(remaining, ["sess-2--pr-rules", "warned--sess-1"])

    def test_rearm_sanitizes_session_id(self):
        self._touch("weird-session--pr-rules")
        engine.rearm({"session_id": "weird/session", "source": "compact"}, self.tmp)
        self.assertEqual(os.listdir(self.state), [])

    def test_rearm_logs_rearm_event(self):
        self._touch("sess-1--pr-rules")
        engine.rearm({"session_id": "sess-1", "source": "compact"}, self.tmp)
        log_dir = os.path.join(self.tmp, ".claude", "ziptie", "logs")
        entries = []
        for fn in os.listdir(log_dir):
            with open(os.path.join(log_dir, fn)) as f:
                entries += [json.loads(ln) for ln in f if ln.strip()]
        rearms = [e for e in entries if e["decision"] == "rearm"]
        self.assertEqual(len(rearms), 1)
        self.assertEqual(rearms[0]["rule"], "(compact)")  # 문자열 — None 금지
        self.assertEqual(rearms[0]["count"], 1)

    def test_rearm_no_markers_no_log(self):
        engine.rearm({"session_id": "sess-1", "source": "compact"}, self.tmp)
        self.assertFalse(
            os.path.exists(os.path.join(self.tmp, ".claude", "ziptie", "logs"))
        )

    def test_rearm_never_raises(self):
        engine.rearm({"session_id": "sess-1"}, "/nonexistent/dir")  # 예외 없이 통과
        engine.rearm({}, self.tmp)
        engine.rearm(None, self.tmp)

    def test_rearm_session_id_warned_removes_delivery_markers_keeps_suppression(self):
        # Session id "warned" collides with warned-- prefix.
        # Delivery marker: warned--pr-rules (for session "warned")
        # Suppression marker: warned--warned (warning already shown)
        # After rearm, only suppression marker should remain.
        self._touch("warned--pr-rules")
        self._touch("warned--warned")
        engine.rearm({"session_id": "warned", "source": "compact"}, self.tmp)
        remaining = sorted(os.listdir(self.state))
        self.assertEqual(remaining, ["warned--warned"])
