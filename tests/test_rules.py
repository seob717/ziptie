import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.rules import parse_rule_file, load_rules

VALID = """---
name: pr-rules
trigger:
  tool: Bash
  pattern: gh\\s+pr\\s+create
source: docs/pr-rules.md
strength: require-read
enabled: true
---
PR 생성 전 docs/pr-rules.md를 반영해.
"""


def _write(dirpath, fname, content):
    path = os.path.join(dirpath, fname)
    with open(path, "w") as f:
        f.write(content)
    return path


def test_parse_valid_rule():
    with tempfile.TemporaryDirectory() as d:
        rule = parse_rule_file(_write(d, "r.md", VALID))
    assert rule.name == "pr-rules"
    assert rule.tool == "Bash"
    assert rule.pattern == "gh\\s+pr\\s+create"
    assert rule.source == "docs/pr-rules.md"
    assert rule.strength == "require-read"
    assert rule.enabled is True
    assert "반영해" in rule.body


def test_parse_no_frontmatter_returns_none():
    with tempfile.TemporaryDirectory() as d:
        assert parse_rule_file(_write(d, "r.md", "그냥 텍스트")) is None


def test_parse_defaults():
    minimal = "---\nname: x\ntrigger:\n  tool: Bash\n  pattern: foo\n---\nbody"
    with tempfile.TemporaryDirectory() as d:
        rule = parse_rule_file(_write(d, "r.md", minimal))
    assert rule.strength == "require-read"  # 기본 강도
    assert rule.enabled is True  # 기본 활성
    assert rule.source is None


def test_unknown_strength_falls_back_to_require_read():
    injected = VALID.replace("strength: require-read", "strength: inject")
    with tempfile.TemporaryDirectory() as d:
        rule = parse_rule_file(_write(d, "r.md", injected))
    assert rule is not None
    assert rule.strength == "require-read"


def test_invalid_name_with_slash_returns_none_with_warning(capsys):
    injected = VALID.replace("name: pr-rules", "name: a/b")
    with tempfile.TemporaryDirectory() as d:
        rule = parse_rule_file(_write(d, "r.md", injected))
    assert rule is None
    err = capsys.readouterr().err
    assert "invalid name" in err
    assert "a/b" in err


def test_invalid_name_uppercase_returns_none_with_warning(capsys):
    injected = VALID.replace("name: pr-rules", "name: PR-Rules")
    with tempfile.TemporaryDirectory() as d:
        rule = parse_rule_file(_write(d, "r.md", injected))
    assert rule is None
    err = capsys.readouterr().err
    assert "invalid name" in err
    assert "PR-Rules" in err


def test_enabled_typo_value_warns_and_stays_true(capsys):
    injected = VALID.replace("enabled: true", "enabled: flase")
    with tempfile.TemporaryDirectory() as d:
        rule = parse_rule_file(_write(d, "r.md", injected))
    assert rule.enabled is True
    err = capsys.readouterr().err
    assert "flase" in err


def test_load_rules_filters_disabled_and_broken():
    with tempfile.TemporaryDirectory() as d:
        rules_dir = os.path.join(d, ".claude", "rules")
        os.makedirs(rules_dir)
        _write(rules_dir, "ok.md", VALID)
        _write(rules_dir, "off.md", VALID.replace("enabled: true", "enabled: false"))
        _write(rules_dir, "broken.md", "---\nname: [invalid\n---\nbody")
        rules = load_rules(d)
    assert [r.name for r in rules] == ["pr-rules"]
