import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pilot.grade_compile_bench import (
    check_rule_form,
    grade_doc,
    smoke_bash,
    smoke_content,
)


def _rule(**kw):
    base = {
        "name": "r",
        "tool": "Bash",
        "pattern": "gh\\s+pr\\s+create",
        "field": None,
        "path": None,
        "strength": "require-read",
        "evidence": "원문",
    }
    base.update(kw)
    return base


def test_check_rule_form_valid_bash():
    r = check_rule_form(_rule())
    assert r["regex_ok"] and r["tool_ok"] and r["content_path_ok"]


def test_check_rule_form_invalid_regex():
    assert check_rule_form(_rule(pattern="[unclosed"))["regex_ok"] is False


def test_check_rule_form_invalid_tool():
    assert check_rule_form(_rule(tool="Read"))["tool_ok"] is False


def test_check_rule_form_content_rule_requires_path():
    # compile.md(392505d): content 룰(field 지정)은 path 필수
    no_path = _rule(tool="Edit", pattern="console\\.log", field="new_string")
    assert check_rule_form(no_path)["content_path_ok"] is False
    with_path = _rule(
        tool="Edit", pattern="console\\.log", field="new_string", path="\\.tsx?$"
    )
    assert check_rule_form(with_path)["content_path_ok"] is True


def test_check_rule_form_invalid_path_regex():
    r = _rule(tool="Edit", pattern="x", field="new_string", path="[bad")
    assert check_rule_form(r)["regex_ok"] is False


def test_smoke_bash_benign_commands_no_match():
    assert smoke_bash(_rule()) == []


def test_smoke_bash_broad_pattern_catches_benign():
    hits = smoke_bash(_rule(pattern="git"))
    assert "git status" in hits


def test_smoke_bash_ignores_non_bash():
    assert smoke_bash(_rule(tool="Edit", pattern="git")) == []


def test_smoke_content_path_filters_markdown():
    scoped = _rule(tool="Edit", pattern="as any", field="new_string", path="\\.tsx?$")
    assert smoke_content(scoped) == []


def test_smoke_content_missing_path_is_fp():
    unscoped = _rule(tool="Edit", pattern="as any", field="new_string")
    assert len(smoke_content(unscoped)) > 0


def test_smoke_content_ignores_non_field_rules():
    assert smoke_content(_rule(tool="Edit", pattern="migrations/")) == []


def test_grade_doc_aggregates():
    data = {
        "doc": "d1",
        "rules": [
            _rule(),
            _rule(name="c", tool="Edit", pattern="as any", field="new_string"),
        ],
        "uncompilable": ["톤 가이드"],
    }
    g = grade_doc(data)
    assert g["doc"] == "d1"
    assert g["n_rules"] == 2
    assert g["n_uncompilable"] == 1
    assert g["form_ok"] == 1  # content 룰이 path 누락으로 form 실패
    assert g["bash_fp"] == 0
    assert g["content_fp"] == 1
    assert g["strengths"] == {"require-read": 2}
