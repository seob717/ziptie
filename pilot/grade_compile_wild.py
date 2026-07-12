#!/usr/bin/env python3
"""야생 ko 컴파일 측정 집계 (DESIGN-compile-wild-ko §5, stdlib only).

grade_compile_multilingual.py의 M1/M2/M4/M5 + evidence 대조를 gold-dir
파라미터화해 재사용한 변형. 게이트 없음(관찰 파일럿) — M3 스모크는
사전등록에 없으므로 계산하지 않는다.
"""

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).parent
WILD = REPO / "compile-wild"

DOCS = ["pinpoint", "dmnote", "token-monitor", "3dollars-ios"]
TOOLS = {"Bash", "Edit", "Write"}
STRENGTHS = {"block", "require-read", "inject"}
MISS_CATS = {"implicit", "structure", "reference-depth", "other"}
UNMATCHED = {"gold-miss", "over-extraction", "duplicate"}


def load(p):
    with open(p) as f:
        return json.load(f)


def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold-dir", type=pathlib.Path, default=WILD / "gold")
    ap.add_argument("--outputs-dir", type=pathlib.Path, default=WILD / "outputs")
    ap.add_argument("--matches-dir", type=pathlib.Path, default=WILD / "matches")
    ap.add_argument("--corpus-dir", type=pathlib.Path, default=WILD / "corpus")
    args = ap.parse_args()

    gold, outputs, matches = {}, {}, {}
    for doc in DOCS:
        gold[doc] = {g["id"]: g for g in load(args.gold_dir / f"{doc}.json")["rules"]}
        outputs[doc] = load(args.outputs_dir / f"{doc}.json")
        matches[doc] = load(args.matches_dir / f"{doc}.json")

    # ---- 무결성 ----
    bad = False
    for doc in DOCS:
        m, out = matches[doc], outputs[doc]
        names = {r["name"] for r in out["rules"]}
        seen = [x["gold_id"] for x in m["matches"]] + [
            x["gold_id"] for x in m["misses"]
        ]
        if sorted(seen) != sorted(gold[doc]):
            print(f"[무결성] {doc}: gold id 불일치 seen={sorted(seen)}")
            bad = True
        used = [x["output_rule"] for x in m["matches"]]
        if len(used) != len(set(used)):
            print(f"[무결성] {doc}: output_rule 중복 매치")
            bad = True
        for name in used + [u["output_rule"] for u in m["unmatched_extracted"]]:
            if name not in names:
                print(f"[무결성] {doc}: 실재하지 않는 output_rule {name}")
                bad = True
        for x in m["misses"]:
            if x["category"] not in MISS_CATS:
                print(f"[무결성] {doc}: miss category 어휘 밖 {x['category']}")
                bad = True
        for u in m["unmatched_extracted"]:
            if u["class"] not in UNMATCHED:
                print(f"[무결성] {doc}: unmatched class 어휘 밖 {u['class']}")
                bad = True
    if bad:
        print("무결성 위반 — 집계 중단")
        sys.exit(1)

    # ---- M1 recall + 미스 분류 ----
    print("## M1 recall / 미스 category")
    for doc in DOCS:
        m = matches[doc]
        cats = {}
        for x in m["misses"]:
            cats[x["category"]] = cats.get(x["category"], 0) + 1
        cat_s = ", ".join(f"{k}:{v}" for k, v in sorted(cats.items()))
        print(
            f"{doc}: {len(m['matches'])}/{len(gold[doc])}"
            + (f" | 미스 {cat_s}" if cats else "")
        )

    # ---- M2 형식 ----
    print("\n## M2 형식 품질 (위반 룰 수 / 추출 룰 수)")
    for doc in DOCS:
        viol, notes = 0, []
        for r in outputs[doc]["rules"]:
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
        print(f"{doc}: {viol}/{len(outputs[doc]['rules'])}")
        for n in notes:
            print(n)

    # ---- M4 unmatched 분류 ----
    print("\n## M4 unmatched 분류")
    for doc in DOCS:
        m = matches[doc]
        cls = {}
        for u in m["unmatched_extracted"]:
            cls[u["class"]] = cls.get(u["class"], 0) + 1
        print(
            f"{doc}: "
            + (", ".join(f"{k}:{v}" for k, v in sorted(cls.items())) or "없음")
        )
        for u in m["unmatched_extracted"]:
            if u["class"] == "over-extraction":
                print(f"  - OE: {u['output_rule']}: {u['note']}")

    # ---- M5 strength + evidence ----
    print("\n## M5 strength (gold 기대 대비) + evidence 대조")
    for doc in DOCS:
        m, out = matches[doc], outputs[doc]
        by = {r["name"]: r for r in out["rules"]}
        text = norm_ws((args.corpus_dir / f"{doc}.md").read_text())
        cells, ev_missing = {}, []
        for mt in m["matches"]:
            g = gold[doc][mt["gold_id"]]
            r = by[mt["output_rule"]]
            key = (g.get("strength", "?"), r["strength"])
            cells[key] = cells.get(key, 0) + 1
            if norm_ws(r.get("evidence", "")) not in text:
                ev_missing.append(r["name"])
        agree = sum(v for (a, b), v in cells.items() if a == b)
        total = sum(cells.values())
        conf = ", ".join(
            f"{a}→{b}:{v}" for (a, b), v in sorted(cells.items()) if a != b
        )
        print(
            f"{doc}: 일치 {agree}/{total}"
            + (f" | 불일치: {conf}" if conf else "")
            + (
                f" | evidence 미일치 {len(ev_missing)}건: {ev_missing}"
                if ev_missing
                else ""
            )
        )


if __name__ == "__main__":
    main()
