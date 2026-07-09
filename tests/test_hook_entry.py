import json
import os
import subprocess
import sys
import tempfile

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


def run_hook(input_data, cwd, env_overrides=None):
    # 부모 프로세스의 CLAUDE_PROJECT_DIR을 상속하면 테스트가 비결정적이 되므로
    # 기본적으로 제거하고, 필요할 때만 env_overrides로 명시적으로 설정한다.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=10,
        env=env,
    )


def make_project():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, ".claude", "rules"))
    with open(os.path.join(d, ".claude", "rules", "pr.md"), "w") as f:
        f.write(RULE)
    return d


def test_deny_then_allow_roundtrip():
    d = make_project()
    inp = {
        "hook_event_name": "PreToolUse",
        "session_id": "s1",
        "tool_name": "Bash",
        "tool_input": {"command": "gh pr create"},
    }
    first = run_hook(inp, d)
    assert first.returncode == 0
    assert (
        json.loads(first.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    )
    second = run_hook(inp, d)
    assert second.returncode == 0
    assert second.stdout.strip() == ""


def test_env_project_dir_takes_precedence_over_input_cwd():
    env_project = make_project()  # pr-rules 있음 → deny
    input_cwd_project = tempfile.mkdtemp()  # 룰 없음 → allow
    inp = {
        "hook_event_name": "PreToolUse",
        "session_id": "s-env",
        "tool_name": "Bash",
        "tool_input": {"command": "gh pr create"},
        "cwd": input_cwd_project,
    }
    result = run_hook(
        inp, input_cwd_project, env_overrides={"CLAUDE_PROJECT_DIR": env_project}
    )
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_garbage_stdin_exits_zero_silently():
    d = make_project()
    r = subprocess.run(
        [sys.executable, HOOK],
        input="not json",
        capture_output=True,
        text=True,
        cwd=d,
        timeout=10,
    )
    assert r.returncode == 0 and r.stdout.strip() == ""
