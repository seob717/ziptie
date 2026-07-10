import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pilot"))
import compaction_runner as cr


def test_conditions_include_two_compact():
    assert set(cr.CONDITIONS) == {"AC", "ZC", "AC2", "ZC2"}


def test_is_two_compact():
    assert cr.is_two_compact("AC2") and cr.is_two_compact("ZC2")
    assert not cr.is_two_compact("AC") and not cr.is_two_compact("ZC")


def test_default_timeout_per_condition():
    # DESIGN-compaction.md §3 25분 / DESIGN-compaction-followup.md §3.2 35분
    assert cr.default_timeout("AC") == 25 * 60
    assert cr.default_timeout("ZC") == 25 * 60
    assert cr.default_timeout("AC2") == 35 * 60
    assert cr.default_timeout("ZC2") == 35 * 60


def _settings(condition):
    cfg = cr.RunConfig(condition, f"{condition}-t", "sonnet", 60)
    return cr.build_settings(cfg)


def test_build_settings_ac2_mirrors_ac_observer_only():
    for cond in ("AC", "AC2"):
        s = _settings(cond)
        assert "PreToolUse" not in s["hooks"]
        compact_hooks = s["hooks"]["SessionStart"][0]["hooks"]
        assert len(compact_hooks) == 1  # 관측 훅만
        assert "observer_sessionstart.py" in compact_hooks[0]["command"]


def test_build_settings_zc2_mirrors_zc_nunchi_hooks():
    for cond in ("ZC", "ZC2"):
        s = _settings(cond)
        assert "PreToolUse" in s["hooks"]
        compact_hooks = s["hooks"]["SessionStart"][0]["hooks"]
        assert len(compact_hooks) == 2  # 재무장 훅(앞) + 관측 훅
        assert "sessionstart.py" in compact_hooks[0]["command"]
        assert "observer_sessionstart.py" in compact_hooks[1]["command"]


def test_stage_messages_two_compact():
    # 3단 시퀀스: STAGE1 → compact → STAGE2B(재독·커밋, PR 금지) → compact → STAGE2(=최종, PR)
    assert "PR은 아직 만들지 마" in cr.STAGE2B_MSG
    assert "## 경고 분석" in cr.STAGE2B_MSG
    assert "server.log" in cr.STAGE2B_MSG
    assert "PR을 생성" in cr.STAGE2_MSG
