import glob, json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
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
    return {"hook_event_name": "PreToolUse", "session_id": session,
            "tool_name": tool, "tool_input": {"command": command}}

def test_first_match_denies_with_source_content():
    d = make_project()
    out = decide(hook_input(), d)
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert "[LAB-123]" in hso["permissionDecisionReason"]      # 원본 문서가 배달됨
    assert "ziptie" in hso["permissionDecisionReason"]

def test_second_call_same_session_allows():
    d = make_project()
    decide(hook_input(session="s2"), d)
    assert decide(hook_input(session="s2"), d) == {}

def test_different_session_denies_again():
    d = make_project()
    decide(hook_input(session="s3"), d)
    assert decide(hook_input(session="s4"), d)["hookSpecificOutput"]["permissionDecision"] == "deny"

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
    inp = {"hook_event_name": "PreToolUse", "session_id": "s6", "tool_name": "Edit",
           "tool_input": {"file_path": "src/a.test.ts", "new_string": "x"}}
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

def test_broken_regex_rule_does_not_disable_others():
    broken = "---\nname: broken-re\ntrigger:\n  tool: Bash\n  pattern: (unbalanced\n---\nb"
    d = make_project()
    with open(os.path.join(d, ".claude", "rules", "aa-broken.md"), "w") as f:
        f.write(broken)  # 정렬상 pr.md보다 먼저 로드되도록 aa- 접두
    out = decide(hook_input(session="s8"), d)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"  # pr-rules는 여전히 발동
