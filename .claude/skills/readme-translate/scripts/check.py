#!/usr/bin/env python3
"""readme-translate 게이트 검사 — 수치 정합·코드 블록 동일성·금지 용어.

사용법: python3 check.py <canonical.md> <translation.md> [--banned 용어 ...]
하드 실패(종료 코드 1): 정본에만 있는 수치, 펜스 코드 블록 불일치, 금지 용어 검출.
소프트 보고(종료 코드 0): 번역본에만 있는 수치, 인라인 코드 스팬 차이 — 수동 확인 대상.
"""

import re
import sys
from collections import Counter

NUM = re.compile(r"\d+(?:[.,]\d+)*%?")
FENCE = re.compile(r"^(```|~~~).*?^\1\s*$", re.M | re.S)
SPAN = re.compile(r"`[^`\n]+`")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main():
    args = sys.argv[1:]
    if "--banned" in args:
        i = args.index("--banned")
        args, banned = args[:i], args[i + 1 :]
    else:
        banned = []
    if len(args) != 2:
        sys.exit(__doc__)
    src, dst = read(args[0]), read(args[1])
    failed = False

    only_src = Counter(NUM.findall(src)) - Counter(NUM.findall(dst))
    if only_src:
        failed = True
        print(f"[하드 실패] 정본에만 있는 수치: {dict(only_src)}")
    only_dst = Counter(NUM.findall(dst)) - Counter(NUM.findall(src))
    if only_dst:
        print(f"[수동 확인] 번역본에만 있는 수치: {dict(only_dst)}")
        print("  → 스냅숏 헤더(버전·커밋)와 영어 서수·수사 표기만 허용된다.")

    src_fences, dst_fences = Counter(FENCE.findall(src)), Counter(FENCE.findall(dst))
    if src_fences != dst_fences:
        failed = True
        for block in (src_fences - dst_fences) | (dst_fences - src_fences):
            print(f"[하드 실패] 펜스 코드 블록 불일치:\n{block[:200]}")

    span_diff = (Counter(SPAN.findall(src)) - Counter(SPAN.findall(dst))) | (
        Counter(SPAN.findall(dst)) - Counter(SPAN.findall(src))
    )
    if span_diff:
        print(
            f"[수동 확인] 인라인 코드 스팬 차이 {len(span_diff)}건: "
            f"{sorted(span_diff)[:10]}"
        )

    for term in banned:
        hits = [
            f"{n}: {line.strip()[:80]}"
            for n, line in enumerate(dst.splitlines(), 1)
            if term in line
        ]
        if hits:
            failed = True
            print(f"[하드 실패] 금지 용어 '{term}' {len(hits)}건:")
            print("\n".join(f"  {h}" for h in hits[:10]))

    print("게이트 실패" if failed else "게이트 통과")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
