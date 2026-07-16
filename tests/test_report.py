import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.report import summarize

RULE = "---\nname: {n}\ntrigger:\n  tool: Bash\n  pattern: x\n---\nb"


def test_summarize_counts_and_dead_rules():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, ".claude", "rules"))
    for n in ("pr-rules", "dead-rule"):
        with open(os.path.join(d, ".claude", "rules", n + ".md"), "w") as f:
            f.write(RULE.format(n=n))
    log_dir = os.path.join(d, ".claude", "nunchi", "logs")
    os.makedirs(log_dir)
    with open(os.path.join(log_dir, "2026-07-09.jsonl"), "w") as f:
        for dec in ("deny", "allow-after-delivery", "allow-after-delivery"):
            f.write(
                json.dumps(
                    {
                        "ts": "t",
                        "session": "s",
                        "rule": "pr-rules",
                        "tool": "Bash",
                        "decision": dec,
                    }
                )
                + "\n"
            )
    result = summarize(d)
    assert result["rules"]["pr-rules"]["deny"] == 1
    assert result["rules"]["pr-rules"]["allow-after-delivery"] == 2
    assert result["never_triggered"] == ["dead-rule"]


def _write_log(d, entries):
    log_dir = os.path.join(d, ".claude", "nunchi", "logs")
    os.makedirs(log_dir)
    with open(os.path.join(log_dir, "2026-07-10.jsonl"), "w") as f:
        for rule, dec in entries:
            f.write(
                json.dumps(
                    {
                        "ts": "t",
                        "session": "s",
                        "rule": rule,
                        "tool": "Edit",
                        "decision": dec,
                    }
                )
                + "\n"
            )


def test_main_output_counts_inject(capsys, monkeypatch):
    d = tempfile.mkdtemp()
    _write_log(d, [("style-rule", "inject"), ("style-rule", "inject")])
    monkeypatch.chdir(d)
    from core.report import main

    main()
    out = capsys.readouterr().out
    assert "inject" in out.splitlines()[0]  # 헤더에 inject 컬럼
    line = next(ln for ln in out.splitlines() if ln.startswith("style-rule"))
    assert "2" in line


def test_main_output_rearm_as_summary_line(capsys, monkeypatch):
    d = tempfile.mkdtemp()
    _write_log(d, [("pr-rules", "deny"), ("(compact)", "rearm")])
    monkeypatch.chdir(d)
    from core.report import main

    main()
    out = capsys.readouterr().out
    # "(compact)"가 룰 행이 아니라 별도 요약 줄로 나온다
    assert not any(ln.startswith("(compact)") for ln in out.splitlines())
    assert "rearm" in out


def test_context_economics_sums_docs_bodies_and_deliveries():
    from core.report import context_economics

    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, ".claude", "rules"))
    os.makedirs(os.path.join(d, "docs"))
    with open(os.path.join(d, "docs", "pr.md"), "w") as f:
        f.write("x" * 1000)
    rule = (
        "---\nname: {n}\ntrigger:\n  tool: Bash\n  pattern: x\n"
        "source: docs/pr.md\n---\n요약 한 줄"
    )
    # 같은 문서를 참조하는 룰 2개 — 문서 크기는 중복 계상하지 않는다
    for n in ("pr-a", "pr-b"):
        with open(os.path.join(d, ".claude", "rules", n + ".md"), "w") as f:
            f.write(rule.format(n=n))
    _write_log(
        d, [("pr-a", "deny"), ("pr-a", "allow-after-delivery"), ("pr-b", "inject")]
    )
    eco = context_economics(d)
    assert eco["n_docs"] == 1
    assert eco["import_bytes"] == 1000
    assert eco["body_bytes"] == 2 * len("요약 한 줄".encode())
    assert (
        eco["deliveries"] == 2
    )  # deny 1 + inject 1 (allow-after-delivery는 배달 아님)
    assert eco["delivered_bytes"] == 2000
    assert (
        eco["sessions_seen"] == 1
    )  # 로그의 고유 세션 수 — 하한 (무배달 세션은 흔적 없음)


def test_context_economics_counts_distinct_sessions():
    import json as _json

    from core.report import context_economics

    d = tempfile.mkdtemp()
    log_dir = os.path.join(d, ".claude", "nunchi", "logs")
    os.makedirs(log_dir)
    with open(os.path.join(log_dir, "2026-07-10.jsonl"), "w") as f:
        for sess in ("s1", "s2", "s2"):
            f.write(
                _json.dumps(
                    {
                        "ts": "t",
                        "session": sess,
                        "rule": "r",
                        "tool": "Bash",
                        "decision": "deny",
                    }
                )
                + "\n"
            )
    assert context_economics(d)["sessions_seen"] == 2


def test_context_economics_no_rules():
    from core.report import context_economics

    d = tempfile.mkdtemp()
    eco = context_economics(d)
    assert eco == {
        "n_docs": 0,
        "import_bytes": 0,
        "body_bytes": 0,
        "deliveries": 0,
        "delivered_bytes": 0,
        "sessions_seen": 0,
        "sessions_tracked": 0,
    }


def test_main_output_session_as_summary_not_rule_row(capsys, monkeypatch):
    d = tempfile.mkdtemp()
    _write_log(d, [("pr-rules", "deny"), ("(session)", "session-start")])
    monkeypatch.chdir(d)
    from core.report import main

    main()
    out = capsys.readouterr().out
    # "(session)"은 룰 행으로 나오지 않는다
    assert not any(ln.startswith("(session)") for ln in out.splitlines())


def test_context_economics_tracked_sessions():
    import json as _json

    from core.report import context_economics

    d = tempfile.mkdtemp()
    log_dir = os.path.join(d, ".claude", "nunchi", "logs")
    os.makedirs(log_dir)
    with open(os.path.join(log_dir, "2026-07-10.jsonl"), "w") as f:
        rows = [
            ("s1", "(session)", "session-start"),  # 훅으로 관측된 세션
            ("s2", "(session)", "session-start"),
            ("s2", "r", "deny"),  # s2는 배달도 있음 — 중복 계상 없음
            ("s3", "r", "deny"),  # 훅 도입 전 로그 — 배달로만 관측
        ]
        for sess, rule, dec in rows:
            f.write(
                _json.dumps(
                    {
                        "ts": "t",
                        "session": sess,
                        "rule": rule,
                        "tool": "InstructionsLoaded",
                        "decision": dec,
                    }
                )
                + "\n"
            )
    eco = context_economics(d)
    assert eco["sessions_seen"] == 3  # s1, s2, s3
    assert eco["sessions_tracked"] == 2  # s1, s2 (session-start 기록이 있는 세션)


def _make_rule_with_source(d, source_text="rules"):
    os.makedirs(os.path.join(d, ".claude", "rules"))
    os.makedirs(os.path.join(d, "docs"))
    rule_path = os.path.join(d, ".claude", "rules", "pr.md")
    with open(rule_path, "w") as f:
        f.write(
            "---\nname: pr-rules\ntrigger:\n  tool: Bash\n  pattern: x\n"
            "source: docs/pr.md\n---\nb"
        )
    src_path = os.path.join(d, "docs", "pr.md")
    with open(src_path, "w") as f:
        f.write(source_text)
    return rule_path, src_path


def test_recompile_candidates_flags_newer_source():
    from core.report import recompile_candidates

    d = tempfile.mkdtemp()
    rule_path, src_path = _make_rule_with_source(d)
    os.utime(rule_path, (1000, 1000))
    os.utime(src_path, (2000, 2000))
    assert recompile_candidates(d) == [("docs/pr.md", ["pr-rules"])]


def test_recompile_candidates_quiet_when_rule_newer():
    from core.report import recompile_candidates

    d = tempfile.mkdtemp()
    rule_path, src_path = _make_rule_with_source(d)
    os.utime(rule_path, (2000, 2000))
    os.utime(src_path, (1000, 1000))
    assert recompile_candidates(d) == []


def test_recompile_candidates_skips_missing_source():
    from core.report import recompile_candidates

    d = tempfile.mkdtemp()
    _, src_path = _make_rule_with_source(d)
    os.remove(src_path)
    assert recompile_candidates(d) == []


def test_context_economics_skips_meta_entries():
    # (recompile) 안내는 룰 배달 지출로 계상하지 않는다
    from core.report import context_economics

    d = tempfile.mkdtemp()
    _write_log(d, [("(recompile)", "inject")])
    assert context_economics(d)["deliveries"] == 0


def test_main_output_recompile_candidate_line(capsys, monkeypatch):
    d = tempfile.mkdtemp()
    rule_path, src_path = _make_rule_with_source(d)
    os.utime(rule_path, (1000, 1000))
    os.utime(src_path, (2000, 2000))
    monkeypatch.chdir(d)
    from core.report import main

    main()
    out = capsys.readouterr().out
    assert "재컴파일 후보: docs/pr.md" in out
    assert "/nunchi:compile docs/pr.md" in out


def test_main_output_recompile_meta_not_a_rule_row(capsys, monkeypatch):
    d = tempfile.mkdtemp()
    _write_log(d, [("pr-rules", "deny"), ("(recompile)", "inject")])
    monkeypatch.chdir(d)
    from core.report import main

    main()
    out = capsys.readouterr().out
    assert not any(ln.startswith("(recompile)") for ln in out.splitlines())


def test_summarize_empty_project():
    d = tempfile.mkdtemp()
    assert summarize(d) == {"rules": {}, "never_triggered": []}


def test_summarize_skips_corrupted_lines():
    d = tempfile.mkdtemp()
    log_dir = os.path.join(d, ".claude", "nunchi", "logs")
    os.makedirs(log_dir)
    with open(os.path.join(log_dir, "2026-07-09.jsonl"), "w") as f:
        f.write("not json\n")
        f.write("null\n")
        f.write("[1, 2]\n")
        f.write(
            json.dumps(
                {
                    "ts": "t",
                    "session": "s",
                    "rule": "pr-rules",
                    "tool": "Bash",
                    "decision": "deny",
                }
            )
            + "\n"
        )
    result = summarize(d)
    assert result["rules"] == {"pr-rules": {"deny": 1}}
