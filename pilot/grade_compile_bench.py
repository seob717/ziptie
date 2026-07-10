"""컴파일 벤치마크 채점기 — DESIGN-compile-bench §4 지표 (stdlib 전용).

입력: pilot/compile-bench/outputs/*.json (§3.1 스키마).
M1 컴파일 가능률 · M2 트리거 형식 품질 · M3 오탐 스모크 · M4 강도 분포를 집계한다.
M4의 evidence 원문 대조는 수기 확인 대상이므로 여기서는 분포·목록만 낸다.
"""

import glob
import json
import os
import re
import sys

VALID_TOOLS = ("Bash", "Edit", "Write")

# §4 M3 — 고정 무해 커맨드 10종 (사전등록 후 변경 금지)
BENIGN_COMMANDS = (
    "git status",
    "ls -la",
    "npm test",
    "git log --oneline",
    "python -m pytest",
    "git add .",
    "gh pr view 12",
    "git diff",
    "echo hello",
    "git checkout -b feat/x",
)

# §4 M3 — content 룰이 걸러내야 할 마크다운 경로
MD_PATHS = ("docs/guide.md", "README.md")


def check_rule_form(rule: dict) -> dict:
    """M2: 정규식 컴파일·tool 유효성·content 룰의 path 동반."""
    regex_ok = True
    try:
        re.compile(rule.get("pattern") or "")
        if rule.get("path"):
            re.compile(rule["path"])
    except re.error:
        regex_ok = False
    tool_ok = rule.get("tool") in VALID_TOOLS
    content_path_ok = not rule.get("field") or bool(rule.get("path"))
    return {
        "regex_ok": regex_ok,
        "tool_ok": tool_ok,
        "content_path_ok": content_path_ok,
    }


def smoke_bash(rule: dict) -> list:
    """M3: Bash 룰 패턴이 무해 커맨드에 걸리면 그 커맨드 목록 (기대: 빈 리스트)."""
    if rule.get("tool") != "Bash":
        return []
    try:
        pat = re.compile(rule.get("pattern") or "")
    except re.error:
        return []
    return [c for c in BENIGN_COMMANDS if pat.search(c)]


def smoke_content(rule: dict) -> list:
    """M3: content 룰이 마크다운 경로 편집에 발화 가능하면 해당 경로 목록.

    path가 없으면 모든 경로에서 발화 가능하므로 전 경로를 오탐으로 친다.
    path 정규식이 깨져 있으면 판단 불가 — 오탐으로 집계하지 않는다 (M2에서 잡힘).
    """
    if not rule.get("field"):
        return []
    if not rule.get("path"):
        return list(MD_PATHS)
    try:
        pat = re.compile(rule["path"])
    except re.error:
        return []
    return [p for p in MD_PATHS if pat.search(p)]


def grade_doc(data: dict) -> dict:
    rules = data.get("rules", [])
    strengths = {}
    form_ok = 0
    bash_fp = 0
    content_fp = 0
    for rule in rules:
        form = check_rule_form(rule)
        if all(form.values()):
            form_ok += 1
        bash_fp += len(smoke_bash(rule))
        content_fp += 1 if smoke_content(rule) else 0
        s = rule.get("strength", "?")
        strengths[s] = strengths.get(s, 0) + 1
    return {
        "doc": data.get("doc", "?"),
        "n_rules": len(rules),
        "n_uncompilable": len(data.get("uncompilable", [])),
        "form_ok": form_ok,
        "bash_fp": bash_fp,
        "content_fp": content_fp,
        "strengths": strengths,
    }


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "compile-bench", "outputs")
    graded = []
    for path in sorted(glob.glob(os.path.join(out_dir, "*.json"))):
        with open(path, encoding="utf-8") as f:
            graded.append(grade_doc(json.load(f)))
    if not graded:
        print("채점할 출력이 없다:", out_dir)
        return 1

    print(
        f"{'doc':<44} {'룰':>3} {'불가':>4} {'형식OK':>6} {'bashFP':>6} {'contFP':>6}  강도"
    )
    tot = {
        "n_rules": 0,
        "n_uncompilable": 0,
        "form_ok": 0,
        "bash_fp": 0,
        "content_fp": 0,
    }
    strengths_total = {}
    for g in graded:
        s = " ".join(f"{k}:{v}" for k, v in sorted(g["strengths"].items()))
        print(
            f"{g['doc']:<44} {g['n_rules']:>3} {g['n_uncompilable']:>4} "
            f"{g['form_ok']:>6} {g['bash_fp']:>6} {g['content_fp']:>6}  {s}"
        )
        for k in tot:
            tot[k] += g[k]
        for k, v in g["strengths"].items():
            strengths_total[k] = strengths_total.get(k, 0) + v
    n, u = tot["n_rules"], tot["n_uncompilable"]
    print(
        f"\n합계: 룰 {n} · 불가 {u} · 컴파일 가능률 {n / (n + u):.0%} · "
        f"형식OK {tot['form_ok']}/{n} · bash 오탐 {tot['bash_fp']} · "
        f"content 오탐 {tot['content_fp']} · 강도 {strengths_total}"
    )

    # M4 수기 확인용 — block 룰 전수와 evidence
    print("\n[block 룰 evidence — 원문 대조 수기 확인 대상]")
    for path in sorted(glob.glob(os.path.join(out_dir, "*.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for rule in data.get("rules", []):
            if rule.get("strength") == "block":
                print(
                    f"- {data.get('doc')} / {rule.get('name')}: {rule.get('evidence', '')[:120]}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
