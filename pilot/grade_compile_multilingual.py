#!/usr/bin/env python3
"""다국어 컴파일 호환성 집계 (DESIGN-compile-multilingual §4, stdlib only).

입력:
  outputs/<doc>.<lang>.json  — 컴파일 출력 {doc, rules[], uncompilable[]}
  matches/<doc>.<lang>.json  — 매칭 판정 {matches, misses, unmatched_extracted}
  gold/<doc>.json            — 93da52e 고정 gold (strength 포함)
  corpus 문서(레포 밖)       — --corpus-dir 로 지정 (evidence 대조용)

M1 recall(문서×언어 + 쌍 차이), M2 형식 품질(룰당 위반율),
M3 오탐 스모크(무해 10종 + content path), M4 날조(over-extraction, microfolio 0룰),
M5 strength confusion(gold 기대 대비, 미스 별도 행) + evidence 실재 대조.
"""

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).parent
ML = REPO / "compile-multilingual"
GOLD_DIR = REPO / "compile-recall" / "gold"

DOCS = ["langgraph", "supabase", "nextjs", "microfolio"]
RULE_DOCS = ["langgraph", "supabase", "nextjs"]  # gold 있는 문서
LANGS = ["en", "ko", "ja", "es"]
TOOLS = {"Bash", "Edit", "Write"}
STRENGTHS = {"block", "require-read", "inject"}

BENIGN = [
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
]
CONTENT_PATHS = ["docs/guide.md", "README.md"]


def load(p):
    with open(p) as f:
        return json.load(f)


def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def integrity(doc, match, gold_ids, output_names):
    errs = []
    seen = [m["gold_id"] for m in match["matches"]] + [
        m["gold_id"] for m in match["misses"]
    ]
    if sorted(seen) != sorted(gold_ids):
        extra = set(seen) - set(gold_ids)
        missing = set(gold_ids) - set(seen)
        dup = {g for g in seen if seen.count(g) > 1}
        errs.append(
            f"gold id 불일치: extra={sorted(extra)} missing={sorted(missing)} dup={sorted(dup)}"
        )
    used = [m["output_rule"] for m in match["matches"]]
    if len(used) != len(set(used)):
        errs.append("output_rule 중복 매치")
    for name in used + [u["output_rule"] for u in match["unmatched_extracted"]]:
        if name not in output_names:
            errs.append(f"실재하지 않는 output_rule: {name}")
    for m in match["misses"]:
        if m["category"] not in {"implicit", "structure", "reference-depth", "other"}:
            errs.append(f"miss category 어휘 밖: {m['category']}")
    for u in match["unmatched_extracted"]:
        if u["class"] not in {"gold-miss", "over-extraction", "duplicate"}:
            errs.append(f"unmatched class 어휘 밖: {u['class']}")
    if match.get("gold_amendments"):
        errs.append("gold_amendments 비어있지 않음 (gold 동결 위반)")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", type=pathlib.Path, default=ML / "outputs")
    ap.add_argument("--matches-dir", type=pathlib.Path, default=ML / "matches")
    ap.add_argument(
        "--corpus-dir",
        type=pathlib.Path,
        required=True,
        help="en 원문 + 번역본(<doc>.<lang>.md)이 모인 디렉터리",
    )
    args = ap.parse_args()

    outputs, matches, gold = {}, {}, {}
    for doc in RULE_DOCS:
        gold[doc] = {g["id"]: g for g in load(GOLD_DIR / f"{doc}.json")["rules"]}
    for doc in DOCS:
        for lang in LANGS:
            p = args.outputs_dir / f"{doc}.{lang}.json"
            outputs[(doc, lang)] = load(p) if p.exists() else None
    for doc in RULE_DOCS:
        for lang in LANGS:
            p = args.matches_dir / f"{doc}.{lang}.json"
            matches[(doc, lang)] = load(p) if p.exists() else None

    # ---- 무결성 ----
    bad = False
    for (doc, lang), m in matches.items():
        if m is None:
            print(f"[무결성] {doc}.{lang}: matches 파일 없음")
            continue
        out = outputs[(doc, lang)]
        names = {r["name"] for r in out["rules"]} if out else set()
        for e in integrity(doc, m, list(gold[doc]), names):
            print(f"[무결성] {doc}.{lang}: {e}")
            bad = True
    if bad:
        print("무결성 위반 — 집계 중단")
        sys.exit(1)

    # ---- M1 recall ----
    print("\n## M1 recall (matches / gold)")
    print("| doc | " + " | ".join(LANGS) + " | (L−en) ko/ja/es |")
    for doc in RULE_DOCS:
        row, diffs = [], []
        n_gold = len(gold[doc])
        for lang in LANGS:
            m = matches[(doc, lang)]
            row.append(f"{len(m['matches'])}/{n_gold}" if m else "실패")
        en = len(matches[(doc, "en")]["matches"]) if matches[(doc, "en")] else 0
        for lang in ["ko", "ja", "es"]:
            m = matches[(doc, lang)]
            diffs.append(f"{(len(m['matches']) - en):+d}" if m else "—")
        print(f"| {doc} | " + " | ".join(row) + " | " + " ".join(diffs) + " |")

    # ---- M2 형식 품질 ----
    print("\n## M2 형식 품질 (위반 룰 수 / 추출 룰 수)")
    for (doc, lang), out in sorted(outputs.items()):
        if out is None:
            print(f"{doc}.{lang}: 컴파일 실패 (ITT: 0룰)")
            continue
        viol = 0
        notes = []
        for r in out["rules"]:
            v = []
            try:
                re.compile(r["pattern"])
            except re.error as e:
                v.append(f"regex 실패({e})")
            if r["tool"] not in TOOLS:
                v.append(f"tool={r['tool']}")
            if r.get("field") and not r.get("path"):
                v.append("field 있는데 path 없음")
            if r["strength"] not in STRENGTHS:
                v.append(f"strength={r['strength']}")
            if v:
                viol += 1
                notes.append(f"  - {r['name']}: {'; '.join(v)}")
        print(f"{doc}.{lang}: {viol}/{len(out['rules'])}")
        for n in notes:
            print(n)

    # ---- M3 오탐 스모크 ----
    print("\n## M3 오탐 스모크 (정탐 2쌍은 RESULTS에서 의도 기준 수기 판정)")
    for (doc, lang), out in sorted(outputs.items()):
        if not out:
            continue
        hits = []
        for r in out["rules"]:
            try:
                pat = re.compile(r["pattern"])
            except re.error:
                continue
            if r["tool"] == "Bash":
                for cmd in BENIGN:
                    if pat.search(cmd):
                        hits.append(f"  - {r['name']} × `{cmd}`")
            elif r.get("field"):
                path_re = r.get("path")
                for p in CONTENT_PATHS:
                    if not path_re or re.search(path_re, p):
                        hits.append(
                            f"  - {r['name']} × path `{p}`"
                            + ("" if path_re else " (path 부재 — 자동 오탐)")
                        )
        if hits:
            print(f"{doc}.{lang}: {len(hits)}건")
            for h in hits:
                print(h)

    # ---- M4 날조 ----
    print("\n## M4 날조")
    for (doc, lang), m in sorted(matches.items()):
        if not m:
            continue
        oe = [u for u in m["unmatched_extracted"] if u["class"] == "over-extraction"]
        gm = [u for u in m["unmatched_extracted"] if u["class"] == "gold-miss"]
        du = [u for u in m["unmatched_extracted"] if u["class"] == "duplicate"]
        print(
            f"{doc}.{lang}: over-extraction {len(oe)}, gold-miss {len(gm)}, duplicate {len(du)}"
        )
        for u in oe:
            print(f"  - OE: {u['output_rule']}: {u['note']}")
    print("microfolio (룰 0 기대):")
    for lang in LANGS:
        out = outputs[("microfolio", lang)]
        n = len(out["rules"]) if out else "실패"
        print(
            f"  microfolio.{lang}: {n}룰"
            + ("" if out and not out["rules"] else " ⚠️" if out else "")
        )

    # ---- M5 strength confusion + evidence 대조 ----
    print("\n## M5 strength (gold 기대 대비; 미스는 별도 행)")
    for doc in RULE_DOCS:
        for lang in LANGS:
            m = matches[(doc, lang)]
            out = outputs[(doc, lang)]
            if not m or not out:
                continue
            by_name = {r["name"]: r for r in out["rules"]}
            cells = {}
            ev_missing = []
            doc_file = args.corpus_dir / (
                f"{doc}.md" if lang == "en" else f"{doc}.{lang}.md"
            )
            doc_text = norm_ws(doc_file.read_text()) if doc_file.exists() else None
            for mt in m["matches"]:
                g = gold[doc][mt["gold_id"]]
                r = by_name[mt["output_rule"]]
                key = (g.get("strength", "?"), r["strength"])
                cells[key] = cells.get(key, 0) + 1
                if (
                    doc_text is not None
                    and norm_ws(r.get("evidence", "")) not in doc_text
                ):
                    ev_missing.append(r["name"])
            n_miss = len(m["misses"])
            agree = sum(v for (a, b), v in cells.items() if a == b)
            total = sum(cells.values())
            conf = ", ".join(
                f"{a}→{b}:{v}" for (a, b), v in sorted(cells.items()) if a != b
            )
            print(
                f"{doc}.{lang}: 일치 {agree}/{total} (미스 {n_miss}건 별도)"
                + (f" | 불일치: {conf}" if conf else "")
                + (
                    f" | evidence 원문 미실재 {len(ev_missing)}건: {ev_missing}"
                    if ev_missing
                    else ""
                )
            )


if __name__ == "__main__":
    main()
