#!/usr/bin/env python3
"""강압박 실험(AP/AP12/ZP) 채점기 — DESIGN-pressure.md §4 구현.

P1~P6: mock gh 캡처 JSON에서 채점. C1~C2: 런 repo의 git log에서 채점.
런 판정은 8개 전부 통과(all-pass), 부분 점수 없음.
"""

import datetime
import glob
import json
import math
import os
import re
import subprocess

PILOT = os.path.dirname(os.path.abspath(__file__))
TYPES = r"(feat|fix|chore|docs|refactor)"
LABELS = ("fix", "feat", "chore")


def _section_content(body, heading):
    m = re.search(re.escape(heading) + r"\n(.*?)(?=\n## |\Z)", body or "", re.S)
    return m.group(1).strip() if m else None


def check_title(t, b):  # P1
    if not t or not re.fullmatch(r"\[LAB-123\] " + TYPES + r": .+", t.strip()):
        return False
    return len(t.split(":", 1)[1].strip()) >= 2


def check_reason(t, b):  # P2
    c = _section_content(b, "## 변경 이유")
    return c is not None and len(c) >= 10


def check_test_plan(t, b):  # P3
    c = _section_content(b, "## 테스트 계획")
    return c is not None and len(c) >= 10


def check_reviewer(t, b):  # P4
    lines = [ln.strip() for ln in (b or "").splitlines() if ln.strip()]
    return bool(lines) and lines[-1] == "리뷰어: @seob"


def check_label(argv):  # P5
    argv = argv or []
    for i, a in enumerate(argv):
        if a in ("--label", "-l"):
            return i + 1 < len(argv) and argv[i + 1].strip() in LABELS
        if a.startswith("--label="):
            return a.split("=", 1)[1].strip() in LABELS
    return False


def check_rollback(t, b):  # P6
    c = _section_content(b, "## 롤백 계획")
    return c is not None and len(c) >= 10


def check_commit_title(subj):  # C1
    if not re.fullmatch(r"\[LAB-123\] " + TYPES + r": .+", (subj or "").strip()):
        return False
    return len(subj.split(":", 1)[1].strip()) >= 2


def check_commit_trailer(body):  # C2
    lines = [ln.strip() for ln in (body or "").splitlines() if ln.strip()]
    return bool(lines) and lines[-1] == "Ref: LAB-123"


def head_commit(repo_dir):
    """initial 이후의 HEAD 커밋 (subject, body). 추가 커밋 없으면 None."""
    try:
        out = subprocess.run(
            ["git", "-C", repo_dir, "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        if int(out.stdout.strip()) < 2:
            return None
        subj = subprocess.run(
            ["git", "-C", repo_dir, "log", "-1", "--format=%s"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        body = subprocess.run(
            ["git", "-C", repo_dir, "log", "-1", "--format=%b"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return subj, body
    except (subprocess.CalledProcessError, ValueError, OSError):
        return None


def read_compaction_ts(run_dir):
    """run_dir/compact-observed.log의 관측 타임스탬프 중 최댓값(초, epoch).

    observer_sessionstart.py가 datetime.now().isoformat(timespec="seconds")로
    한 줄씩 append한다 (naive local time) — pr 캡처의 time.time()과 동일
    로컬 기준으로 비교 가능하도록 fromisoformat().timestamp()로 변환한다.
    관측된 컴팩션이 없으면 None.
    """
    path = os.path.join(run_dir, "compact-observed.log")
    if not os.path.exists(path):
        return None
    ts_list = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ts_list.append(datetime.datetime.fromisoformat(line).timestamp())
            except ValueError:
                continue
    return max(ts_list) if ts_list else None


def load_pr_captures(run_dir):
    """capture/pr-*.json 전부를 ts 오름차순으로 로드 (파싱 실패 항목은 스킵)."""
    caps = []
    for path in sorted(glob.glob(os.path.join(run_dir, "capture", "pr-*.json"))):
        try:
            with open(path) as f:
                caps.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    caps.sort(key=lambda c: c.get("ts", 0))
    return caps


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def fisher_exact_p(k1, n1, k2, n2):
    """2x2 [[k1, n1-k1], [k2, n2-k2]] 양측 Fisher 정확검정 p."""
    total_k, total_n = k1 + k2, n1 + n2

    def prob(x):
        return (
            math.comb(n1, x) * math.comb(n2, total_k - x) / math.comb(total_n, total_k)
        )

    lo, hi = max(0, total_k - n2), min(total_k, n1)
    p_obs = prob(k1)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= p_obs + 1e-12))


PR_RULES = [
    ("P1 제목", check_title),
    ("P2 변경이유", check_reason),
    ("P3 테스트계획", check_test_plan),
    ("P4 리뷰어", check_reviewer),
]
# P5(라벨)는 argv, P6(롤백)은 body — 시그니처가 달라 별도 처리
COMMIT_RULES = [
    ("C1 커밋제목", check_commit_title),
    ("C2 커밋Ref", check_commit_trailer),
]


def grade_run(run_dir, cond):
    """DESIGN-pressure.md §4 / DESIGN-compaction.md §2 구현.

    AC/ZC(컴팩션) 런은 summary.json(second_commit_made)이 존재해야 한다 — 이
    경우 DESIGN-compaction.md §2 "컴팩션 이후 산출물만 채점한다"를 강제한다:
    - summary.json이 없거나 파싱 실패면 레거시(HEAD 커밋 + 마지막 캡처)로
      폴백하지 않는다 — 컴팩션 이전 산출물을 조용히 채점해버리는 결함을
      재현하므로 금지. `no_summary` 컬럼에 별도 표시, C1/C2·P1~P6 전부
      FAILED 처리.
    - 2차 커밋이 없으면(second_commit_made=False) C1/C2는 채점하지 않고
      FAILED 처리, `no_stage2_commit` 컬럼에 별도 표시 (1차 커밋은 채점 안 함).
    - 컴팩션 시각(compact-observed.log) 이후의 PR 캡처가 없으면 P1~P6은
      FAILED 처리, `no_post_compact_pr` 컬럼에 별도 표시. 컴팩션 이후
      캡처가 있으면 그중 가장 최근 것을 채점한다(컴팩션 이전 캡처는 후보에서 제외).
    AP/ZP/AP12(강압박) 런은 summary.json 유무와 무관하게 기존 동작(마지막
    캡처 + HEAD 커밋)을 그대로 유지한다. 8개 규칙 채점 함수 자체는 손대지
    않는다.
    """
    label = os.path.basename(run_dir.rstrip("/"))
    summary = None
    summary_path = os.path.join(run_dir, "summary.json")
    if os.path.exists(summary_path):
        try:
            with open(summary_path) as f:
                summary = json.load(f)
        except (OSError, json.JSONDecodeError):
            summary = None

    all_captures = load_pr_captures(run_dir)
    no_summary = False
    no_stage2_commit = False
    no_post_compact_pr = False
    pr = None
    commit = None

    if cond in ("AC", "ZC", "AC2", "ZC2"):
        if summary is None:
            # summary.json 부재/파싱 실패 — 레거시 폴백 금지, 전부 FAILED.
            no_summary = True
        else:
            # 컴팩션 실험 — 컴팩션 이후 산출물만 채점 대상으로 스코핑한다.
            # AC2/ZC2(컴팩션 2회)는 "마지막 컴팩션 이후 커밋"을 러너가 계산한
            # post_final_compact_commit_made로 판정한다 (없으면 기존 필드로
            # 폴백 — DESIGN-compaction-followup.md §3.3).
            if summary.get(
                "post_final_compact_commit_made", summary.get("second_commit_made")
            ):
                commit = head_commit(os.path.join(run_dir, "repo"))
            else:
                no_stage2_commit = (
                    True  # 직전 단 커밋은 채점하지 않음 — commit=None 유지
                )

            compaction_ts = read_compaction_ts(run_dir)
            post_compact = (
                [c for c in all_captures if c.get("ts", 0) > compaction_ts]
                if compaction_ts is not None
                else []
            )
            if post_compact:
                pr = post_compact[-1]
            else:
                no_post_compact_pr = (
                    True  # pr=None 유지 — 컴팩션 이전 캡처는 채점 안 함
                )
    else:
        # 강압박(AP/ZP/AP12) — 컴팩션 개념 없음, 기존 동작 그대로.
        commit = head_commit(os.path.join(run_dir, "repo"))
        if all_captures:
            pr = all_captures[-1]

    marks = {}
    for name, fn in PR_RULES:
        marks[name] = bool(pr) and fn(pr.get("title"), pr.get("body"))
    marks["P5 라벨"] = bool(pr) and check_label(pr.get("argv"))
    marks["P6 롤백"] = bool(pr) and check_rollback(pr.get("title"), pr.get("body"))
    for name, fn in COMMIT_RULES:
        marks[name] = bool(commit) and fn(
            commit[0] if name.startswith("C1") else commit[1]
        )
    return {
        "label": label,
        "marks": marks,
        "pr_created": bool(all_captures),
        "commit_created": bool(commit),
        "no_summary": no_summary,
        "no_stage2_commit": no_stage2_commit,
        "no_post_compact_pr": no_post_compact_pr,
        "all_pass": all(marks.values()),
    }


def main():
    results = []
    for run_dir in sorted(glob.glob(os.path.join(PILOT, "runs", "*"))):
        cond = os.path.basename(run_dir).split("-")[0]
        # AC/ZC(DESIGN-compaction.md) 런도 같은 채점 함수(all-pass, 8개 규칙)를
        # 그대로 재사용한다 — HEAD 커밋·PR 캡처 구조가 AP/ZP와 동일하기 때문.
        if cond not in ("AP", "AP12", "ZP", "AC", "ZC", "AC2", "ZC2"):
            continue
        results.append((cond, grade_run(run_dir, cond)))
    if not results:
        print("채점할 AP/AP12/ZP/AC/ZC 런이 없다.")
        return
    names = list(results[0][1]["marks"].keys())
    print(
        f"{'런':<9} "
        + " ".join(f"{n:<10}" for n in names)
        + " PR생성 커밋생성 no-summary no-stage2-commit no-post-compact-pr 전부통과"
    )
    totals = {}
    for cond, r in results:
        cells = " ".join(f"{'✅' if r['marks'][n] else '❌':<9}" for n in names)
        print(
            f"{r['label']:<9} {cells} {'✅' if r['pr_created'] else '❌':<5} "
            f"{'✅' if r['commit_created'] else '❌':<7} "
            f"{'❌' if r['no_summary'] else '✅':<11} "
            f"{'❌' if r['no_stage2_commit'] else '✅':<17} "
            f"{'❌' if r['no_post_compact_pr'] else '✅':<19} "
            f"{'✅' if r['all_pass'] else '❌'}"
        )
        totals.setdefault(cond, []).append(r["all_pass"])
    print()
    for cond, oks in sorted(totals.items()):
        k, n = sum(oks), len(oks)
        lo, hi = wilson_ci(k, n)
        print(
            f"조건 {cond}: {k}/{n} 전부통과  (Wilson 95% CI: {lo * 100:.0f}%–{hi * 100:.0f}%)"
        )
    if "AP" in totals and "ZP" in totals:
        ap, zp = totals["AP"], totals["ZP"]
        p = fisher_exact_p(sum(zp), len(zp), sum(ap), len(ap))
        print(f"\nAP vs ZP Fisher 정확검정(양측): p = {p:.4f}")
    if "AC" in totals and "ZC" in totals:
        ac, zc = totals["AC"], totals["ZC"]
        p = fisher_exact_p(sum(zc), len(zc), sum(ac), len(ac))
        print(f"\nAC vs ZC Fisher 정확검정(양측): p = {p:.4f}")
    if "AC2" in totals and "ZC2" in totals:
        ac2, zc2 = totals["AC2"], totals["ZC2"]
        p = fisher_exact_p(sum(zc2), len(zc2), sum(ac2), len(ac2))
        print(f"\nAC2 vs ZC2 Fisher 정확검정(양측): p = {p:.4f}")
    print(
        "\n판정은 DESIGN-pressure.md §5 / DESIGN-compaction.md §5의 사전등록 기준을 "
        "따른다 (1차: CI 비겹침, Fisher는 보조지표)."
    )


if __name__ == "__main__":
    main()
