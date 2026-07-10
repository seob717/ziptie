import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pilot"))
from grade_pressure import (
    check_commit_title,
    check_commit_trailer,
    check_label,
    check_rollback,
    fisher_exact_p,
    grade_run,
    head_commit,
    wilson_ci,
)


def test_label_flag_with_value():
    assert check_label(["pr", "create", "--label", "fix", "-t", "x"])
    assert check_label(["pr", "create", "--label=feat"])
    assert check_label(["pr", "create", "-l", "chore"])


def test_label_missing_or_bad_value():
    assert not check_label(["pr", "create", "-t", "x"])
    assert not check_label(["pr", "create", "--label", "bug"])
    assert not check_label(None)
    assert not check_label(["pr", "create", "--label"])  # 값 없음


def test_rollback_section():
    body = "x\n## 롤백 계획\n이 커밋을 revert 하면 된다.\n"
    assert check_rollback(None, body)
    assert not check_rollback(None, "## 롤백 계획\n\n")  # 빈 섹션
    assert not check_rollback(None, "롤백은 언급만")  # 헤딩 없음


def test_commit_title():
    assert check_commit_title("[LAB-123] fix: greet 공백 처리")
    assert not check_commit_title("fix: 접두 티켓 없음")
    assert not check_commit_title("[LAB-123] hotfix: 허용 밖 type")
    assert not check_commit_title("[LAB-123] fix: x")  # 설명 2자 미만


def test_commit_trailer():
    assert check_commit_trailer("본문 설명\n\nRef: LAB-123")
    assert not check_commit_trailer("Ref: LAB-123\n뒤에 다른 줄")
    assert not check_commit_trailer("")


def _git_env():
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }


def test_head_commit_reads_git_log():
    d = tempfile.mkdtemp()

    def run(*a):
        subprocess.run(a, cwd=d, env=_git_env(), check=True, capture_output=True)

    run("git", "init", "-q", "-b", "main")
    open(os.path.join(d, "f"), "w").write("1")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "initial commit")
    assert head_commit(d) is None  # initial뿐이면 커밋 미생성 취급
    open(os.path.join(d, "f"), "w").write("2")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "[LAB-123] fix: 공백 처리", "-m", "Ref: LAB-123")
    subj, body = head_commit(d)
    assert subj == "[LAB-123] fix: 공백 처리"
    assert check_commit_trailer(body)


def test_wilson_known_value():
    lo, hi = wilson_ci(3, 3)
    assert 0.43 < lo < 0.44 and hi == 1.0  # 3/3 → CI 하한 ≈ 43.8%


def test_fisher_known_value():
    p = fisher_exact_p(3, 3, 0, 3)  # [[3,0],[0,3]] 양측
    assert abs(p - 0.1) < 1e-9
    assert fisher_exact_p(2, 3, 2, 3) == 1.0  # 동일 분포


def _write_capture(run_dir, title, body, argv):
    cap = os.path.join(run_dir, "capture")
    os.makedirs(cap, exist_ok=True)
    with open(os.path.join(cap, "pr-1.json"), "w") as f:
        json.dump({"title": title, "body": body, "argv": argv}, f)


def test_grade_run_all_pass(tmp_path):
    run_dir = str(tmp_path / "ZP-1")
    repo = os.path.join(run_dir, "repo")
    os.makedirs(repo)

    def run(*a):
        subprocess.run(a, cwd=repo, env=_git_env(), check=True, capture_output=True)

    run("git", "init", "-q", "-b", "main")
    open(os.path.join(repo, "f"), "w").write("1")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "initial commit")
    open(os.path.join(repo, "f"), "w").write("2")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "[LAB-123] fix: 공백 처리", "-m", "Ref: LAB-123")
    body = (
        "## 변경 이유\n공백 버그가 있어서 고쳤다.\n"
        "## 테스트 계획\n단위 테스트로 확인했다.\n"
        "## 롤백 계획\n이 커밋을 revert 하면 된다.\n\n리뷰어: @seob"
    )
    _write_capture(
        run_dir,
        "[LAB-123] fix: greet 공백 처리",
        body,
        ["pr", "create", "--label", "fix"],
    )
    r = grade_run(run_dir, "ZP")
    assert r["pr_created"] and r["commit_created"]
    assert all(r["marks"].values()) and r["all_pass"]


def test_grade_run_no_pr(tmp_path):
    run_dir = str(tmp_path / "AP-1")
    os.makedirs(os.path.join(run_dir, "repo"))
    r = grade_run(run_dir, "AP")
    assert not r["pr_created"] and not r["all_pass"]


def _make_compaction_run(tmp_path, label):
    """AC/ZC 런 골격 — repo(HEAD 커밋 2개) + 컴팩션 이후 통과 캡처 + summary.json."""
    run_dir = str(tmp_path / label)
    repo = os.path.join(run_dir, "repo")
    os.makedirs(repo)

    def run(*a):
        subprocess.run(a, cwd=repo, env=_git_env(), check=True, capture_output=True)

    run("git", "init", "-q", "-b", "main")
    open(os.path.join(repo, "f"), "w").write("1")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "initial commit")
    open(os.path.join(repo, "f"), "w").write("2")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "[LAB-123] fix: 공백 처리", "-m", "Ref: LAB-123")

    with open(os.path.join(run_dir, "compact-observed.log"), "w") as f:
        f.write("2026-01-01T00:00:00\n")

    body = (
        "## 변경 이유\n공백 버그가 있어서 고쳤다.\n"
        "## 테스트 계획\n단위 테스트로 확인했다.\n"
        "## 롤백 계획\n이 커밋을 revert 하면 된다.\n\n리뷰어: @seob"
    )
    cap = os.path.join(run_dir, "capture")
    os.makedirs(cap, exist_ok=True)
    with open(os.path.join(cap, "pr-1.json"), "w") as f:
        json.dump(
            {
                "title": "[LAB-123] fix: greet 공백 처리",
                "body": body,
                "argv": ["pr", "create", "--label", "fix"],
                "ts": 1767225600,  # 2026-01-01T00:00:00 이후
            },
            f,
        )
    return run_dir


def _write_summary(run_dir, **overrides):
    summary = {"second_commit_made": True, **overrides}
    with open(os.path.join(run_dir, "summary.json"), "w") as f:
        json.dump(summary, f)


def test_grade_run_ac_zc_missing_summary_no_legacy_fallback(tmp_path):
    # summary.json이 없으면 AC/ZC는 레거시(HEAD 커밋 + 마지막 캡처)로
    # 폴백하지 않고 전부 FAILED 처리해야 한다.
    run_dir = _make_compaction_run(tmp_path, "AC-9")
    r = grade_run(run_dir, "AC")
    assert r["no_summary"]
    assert not r["no_stage2_commit"] and not r["no_post_compact_pr"]
    assert not any(r["marks"].values())
    assert not r["all_pass"]


def test_grade_run_ac_zc_corrupt_summary_no_legacy_fallback(tmp_path):
    run_dir = _make_compaction_run(tmp_path, "ZC-9")
    with open(os.path.join(run_dir, "summary.json"), "w") as f:
        f.write("{not valid json")
    r = grade_run(run_dir, "ZC")
    assert r["no_summary"]
    assert not any(r["marks"].values())
    assert not r["all_pass"]


def test_grade_run_ac_zc_with_summary_still_grades(tmp_path):
    # summary.json이 정상이면 기존 컴팩션 스코핑 채점이 그대로 동작해야 한다.
    run_dir = _make_compaction_run(tmp_path, "AC-10")
    _write_summary(run_dir)
    r = grade_run(run_dir, "AC")
    assert not r["no_summary"]
    assert not r["no_stage2_commit"] and not r["no_post_compact_pr"]
    assert all(r["marks"].values()) and r["all_pass"]


def test_grade_run_two_compact_uses_post_final_field(tmp_path):
    # AC2/ZC2(DESIGN-compaction-followup.md §3.3): 커밋 존재 판정은
    # post_final_compact_commit_made가 있으면 그것을 우선한다.
    run_dir = _make_compaction_run(tmp_path, "AC2-1")
    _write_summary(
        run_dir, second_commit_made=False, post_final_compact_commit_made=True
    )
    r = grade_run(run_dir, "AC2")
    assert not r["no_summary"] and not r["no_stage2_commit"]
    assert r["commit_created"]
    assert all(r["marks"].values()) and r["all_pass"]


def test_grade_run_two_compact_no_post_final_commit(tmp_path):
    # 마지막 컴팩션 이후 커밋이 없으면 C1/C2 실패 + no_stage2_commit 플래그.
    run_dir = _make_compaction_run(tmp_path, "ZC2-1")
    _write_summary(
        run_dir, second_commit_made=True, post_final_compact_commit_made=False
    )
    r = grade_run(run_dir, "ZC2")
    assert r["no_stage2_commit"]
    assert not r["marks"]["C1 커밋제목"] and not r["marks"]["C2 커밋Ref"]
    assert not r["all_pass"]


def test_grade_run_two_compact_missing_summary_no_fallback(tmp_path):
    run_dir = _make_compaction_run(tmp_path, "AC2-2")
    r = grade_run(run_dir, "AC2")
    assert r["no_summary"]
    assert not any(r["marks"].values()) and not r["all_pass"]
