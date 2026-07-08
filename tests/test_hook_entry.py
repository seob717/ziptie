import json, os, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "pretooluse.py")
RULE = """---
name: pr-rules
trigger:
  tool: Bash
  pattern: gh\\s+pr\\s+create
strength: require-read
---
PR 규칙 본문
"""

def run_hook(input_data, cwd):
    return subprocess.run(
        [sys.executable, HOOK], input=json.dumps(input_data),
        capture_output=True, text=True, cwd=cwd, timeout=10,
    )

def make_project():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, ".claude", "rules"))
    with open(os.path.join(d, ".claude", "rules", "pr.md"), "w") as f:
        f.write(RULE)
    return d

def test_deny_then_allow_roundtrip():
    d = make_project()
    inp = {"hook_event_name": "PreToolUse", "session_id": "s1",
           "tool_name": "Bash", "tool_input": {"command": "gh pr create"}}
    first = run_hook(inp, d)
    assert first.returncode == 0
    assert json.loads(first.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    second = run_hook(inp, d)
    assert second.returncode == 0
    assert second.stdout.strip() == ""

def test_garbage_stdin_exits_zero_silently():
    d = make_project()
    r = subprocess.run([sys.executable, HOOK], input="not json",
                       capture_output=True, text=True, cwd=d, timeout=10)
    assert r.returncode == 0 and r.stdout.strip() == ""
