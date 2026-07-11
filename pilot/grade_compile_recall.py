#!/usr/bin/env python3
"""컴파일 recall 집계기 — DESIGN-compile-recall.md §4.2.

판정(매칭)은 수기다. 이 스크립트는 gold/·matches/·compile-bench outputs/를 읽어
정합성을 검산하고 M1(recall)·M2(미스 분류)·M3(precision 재검) 표를 출력한다.
stdlib 전용.

사용: python3 pilot/grade_compile_recall.py
     [--matches-dir DIR] [--outputs-dir DIR]  # v2 재측정용, 기본값은 v1 경로
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PILOT = Path(__file__).parent
GOLD_DIR = PILOT / "compile-recall" / "gold"
MATCHES_DIR = PILOT / "compile-recall" / "matches"
OUTPUTS_DIR = PILOT / "compile-bench" / "outputs"

MISS_CATEGORIES = {"implicit", "structure", "reference-depth", "other"}
UNMATCHED_CLASSES = {"gold-miss", "over-extraction", "duplicate"}


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check(cond: bool, msg: str, errors: list) -> None:
    if not cond:
        errors.append(msg)


def grade_doc(doc: str, errors: list) -> dict | None:
    gold = load(GOLD_DIR / f"{doc}.json")
    matches_path = MATCHES_DIR / f"{doc}.json"
    if not matches_path.exists():
        print(f"  {doc}: gold 있음, matches 없음 — 대조 미실시로 건너뜀")
        return None
    m = load(matches_path)
    output = load(OUTPUTS_DIR / f"{doc}.json")

    gold_ids = [r["id"] for r in gold["rules"]]
    check(len(gold_ids) == len(set(gold_ids)), f"{doc}: gold 룰 id 중복", errors)
    output_names = {r["name"] for r in output["rules"]}

    matched_ids = [x["gold_id"] for x in m.get("matches", [])]
    missed_ids = [x["gold_id"] for x in m.get("misses", [])]

    # 정합성: 정답 전수가 matches∪misses에 정확히 1회 (§4.2)
    seen = Counter(matched_ids + missed_ids)
    for gid in gold_ids:
        check(
            seen.get(gid, 0) == 1,
            f"{doc}: gold {gid} 판정 {seen.get(gid, 0)}회 (1회여야 함)",
            errors,
        )
    for gid in seen:
        check(gid in gold_ids, f"{doc}: 판정에 등장한 {gid}가 gold에 없음", errors)

    # 정합성: output_rule 실존 + 1:1 매칭 (§4 ③)
    used_outputs = [x["output_rule"] for x in m.get("matches", [])]
    check(
        len(used_outputs) == len(set(used_outputs)),
        f"{doc}: 추출 룰 하나가 정답 여럿에 매칭됨 (1:1 위반)",
        errors,
    )
    for x in m.get("matches", []) + m.get("unmatched_extracted", []):
        check(
            x["output_rule"] in output_names,
            f"{doc}: output_rule '{x['output_rule']}'가 outputs에 없음",
            errors,
        )

    # 정합성: 분류 어휘 (§4.1)
    for x in m.get("misses", []):
        check(
            x["category"] in MISS_CATEGORIES,
            f"{doc}: miss category '{x['category']}' 미정의",
            errors,
        )
    for x in m.get("unmatched_extracted", []):
        check(
            x["class"] in UNMATCHED_CLASSES,
            f"{doc}: unmatched class '{x['class']}' 미정의",
            errors,
        )

    # 정합성: gold-miss는 정답 갱신과 짝 (§4)
    amended = {x["gold_id"] for x in m.get("gold_amendments", [])}
    check(
        amended <= set(gold_ids), f"{doc}: gold_amendments의 id가 gold에 없음", errors
    )

    return {
        "doc": doc,
        "gold": len(gold_ids),
        "matched": len(matched_ids),
        "miss_cats": Counter(x["category"] for x in m.get("misses", [])),
        "unmatched_cls": Counter(x["class"] for x in m.get("unmatched_extracted", [])),
        "extracted": len(output["rules"]),
        "amendments": len(amended),
    }


def main() -> int:
    global MATCHES_DIR, OUTPUTS_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches-dir", type=Path, default=MATCHES_DIR)
    parser.add_argument("--outputs-dir", type=Path, default=OUTPUTS_DIR)
    args = parser.parse_args()
    MATCHES_DIR, OUTPUTS_DIR = args.matches_dir, args.outputs_dir

    if not GOLD_DIR.exists():
        print(f"gold 디렉터리 없음: {GOLD_DIR} — DESIGN-compile-recall.md §3부터 진행")
        return 1
    errors: list = []
    rows = []
    for gold_path in sorted(GOLD_DIR.glob("*.json")):
        if gold_path.name == "TEMPLATE.json":
            continue
        row = grade_doc(gold_path.stem, errors)
        if row:
            rows.append(row)

    if errors:
        print("\n정합성 위반 — 채점 거부 (§4.2):")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    if not rows:
        print("대조 완료된 문서 없음")
        return 1

    print("\n## M1 recall")
    print("| doc | gold | matched | recall | 추출 총수 | 정답 갱신 |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(
            f"| {r['doc']} | {r['gold']} | {r['matched']} | {r['matched'] / r['gold']:.0%} | {r['extracted']} | {r['amendments']} |"
        )
    tg, tm = sum(r["gold"] for r in rows), sum(r["matched"] for r in rows)
    print(f"| **전체(마이크로)** | {tg} | {tm} | **{tm / tg:.0%}** | | |")

    print("\n## M2 미스 분류")
    total_miss = Counter()
    for r in rows:
        total_miss.update(r["miss_cats"])
    for cat in sorted(MISS_CATEGORIES):
        print(f"- {cat}: {total_miss.get(cat, 0)}")

    print("\n## M3 unmatched 추출 룰 분류 (precision 재검)")
    total_un = Counter()
    for r in rows:
        total_un.update(r["unmatched_cls"])
    for cls in sorted(UNMATCHED_CLASSES):
        print(f"- {cls}: {total_un.get(cls, 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
