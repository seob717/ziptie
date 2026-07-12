#!/usr/bin/env python3
"""야생 한국어 CLAUDE.md 표집 (DESIGN-compile-wild-ko §2, stdlib + gh CLI).

고정 쿼리 3종 → 기계 필터(ⓐ~ⓔ) → 별점 내림차순 후보 표 출력.
수기 제외·최종 4건 선정은 사람이 하고 manifest.json으로 동결한다.

usage: sample_wild_ko.py <work-dir>   # 후보 원장·본문 캐시를 work-dir에 저장
"""

import hashlib
import json
import pathlib
import re
import subprocess
import sys
import urllib.request

QUERIES = ["하지 마세요", "해야 합니다", "금지"]
LIMIT = 30
MIN_BYTES, MAX_BYTES = 2_000, 60_000
MIN_HANGUL, MIN_RATIO = 300, 0.3

WORK = pathlib.Path(sys.argv[1])
WORK.mkdir(parents=True, exist_ok=True)
(WORK / "corpus").mkdir(exist_ok=True)

FENCE_RE = re.compile(r"^```.*?^```", re.M | re.S)


def gh(args):
    r = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"gh 실패: {args}\n{r.stderr}")
    return r.stdout


def hangul_stats(text):
    prose = FENCE_RE.sub("", text)
    h = sum(1 for c in prose if "가" <= c <= "힣")
    latin = sum(1 for c in prose if c.isascii() and c.isalpha())
    ratio = h / (h + latin) if (h + latin) else 0.0
    return h, ratio


# 1) 고정 쿼리 합집합
raw = {}
for q in QUERIES:
    out = gh(
        [
            "search",
            "code",
            "--filename",
            "CLAUDE.md",
            q,
            "--limit",
            str(LIMIT),
            "--json",
            "repository,path",
        ]
    )
    for item in json.loads(out):
        repo = item["repository"]["nameWithOwner"]
        path = item["path"]
        raw.setdefault((repo, path), []).append(q)
(WORK / "search-raw.json").write_text(
    json.dumps(
        [{"repo": r, "path": p, "queries": qs} for (r, p), qs in sorted(raw.items())],
        ensure_ascii=False,
        indent=2,
    )
)
print(f"쿼리 합집합: {len(raw)}건")

# 2) 기계 필터
cands, seen_sha = [], set()
for (repo, path), qs in sorted(raw.items()):
    if pathlib.PurePosixPath(path).name != "CLAUDE.md":  # ⓐ
        continue
    owner = repo.split("/")[0]
    if owner.lower() == "seob717":  # ⓔ
        continue
    meta = json.loads(gh(["api", f"repos/{repo}"]))
    if meta.get("fork"):  # ⓔ
        continue
    branch = meta["default_branch"]
    head = json.loads(gh(["api", f"repos/{repo}/commits/{branch}"]))["sha"]
    url = f"https://raw.githubusercontent.com/{repo}/{head}/{path}"
    try:
        body = urllib.request.urlopen(url, timeout=30).read()
    except Exception as e:
        print(f"skip {repo} {path}: fetch 실패 {e}")
        continue
    if not (MIN_BYTES <= len(body) <= MAX_BYTES):  # ⓑ
        continue
    text = body.decode("utf-8", errors="replace")
    h, ratio = hangul_stats(text)
    if h < MIN_HANGUL or ratio < MIN_RATIO:  # ⓒ
        continue
    sha = hashlib.sha256(body).hexdigest()
    if sha in seen_sha:  # ⓓ
        continue
    seen_sha.add(sha)
    cid = repo.replace("/", "__") + (
        "" if path == "CLAUDE.md" else "__" + path.replace("/", "_")
    )
    (WORK / "corpus" / f"{cid}.md").write_bytes(body)
    cands.append(
        {
            "id": cid,
            "repo": repo,
            "path": path,
            "stars": meta["stargazers_count"],
            "pinned_url": url,
            "sha256": sha,
            "bytes": len(body),
            "hangul": h,
            "hangul_ratio": round(ratio, 2),
            "queries": qs,
            "description": (meta.get("description") or "")[:80],
        }
    )

cands.sort(key=lambda c: (-c["stars"], c["repo"]))
(WORK / "candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=2))
print(f"\n기계 필터 통과: {len(cands)}건 (별점 내림차순)")
for c in cands:
    print(
        f"  ★{c['stars']:<6} {c['repo']:<45} {c['bytes']:>6}B 한글{c['hangul']:>5} r={c['hangul_ratio']} | {c['description']}"
    )
