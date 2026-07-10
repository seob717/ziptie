"""ziptie 로그 집계 — 룰별 배달/통과 횟수와 죽은 룰 목록."""

import glob
import json
import os

from core.rules import load_rules


def summarize(project_dir: str) -> dict:
    counts = {}
    for path in sorted(
        glob.glob(os.path.join(project_dir, ".claude", "ziptie", "logs", "*.jsonl"))
    ):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict):
                    continue
                rule_counts = counts.setdefault(entry.get("rule", "?"), {})
                decision = entry.get("decision", "?")
                rule_counts[decision] = rule_counts.get(decision, 0) + 1
    defined = [r.name for r in load_rules(project_dir)]
    return {
        "rules": counts,
        "never_triggered": [n for n in defined if n not in counts],
    }


def context_economics(project_dir: str) -> dict:
    """@import 대비 컨텍스트 절약 추정 (PROBE-context-economics 방법의 레포별 산수).

    - import_bytes: 룰들이 참조하는 source 문서의 합계(중복 제거) —
      이 문서들을 CLAUDE.md에서 @import했다면 매 세션 시작에 실렸을 양.
    - body_bytes: 룰 본문 합계 — ziptie 방식에서 세션 시작에 실리는 양.
    - delivered_bytes: 로그의 배달(deny·inject) 건수 × 현재 문서 크기 근사.
    """
    rules = load_rules(project_dir)
    doc_sizes, body_bytes, rule_doc = {}, 0, {}
    for rule in rules:
        body_bytes += len(rule.body.encode())
        if not rule.source:
            continue
        rule_doc[rule.name] = rule.source
        if rule.source not in doc_sizes:
            try:
                doc_sizes[rule.source] = os.path.getsize(
                    os.path.join(project_dir, rule.source)
                )
            except OSError:
                pass
    deliveries = delivered_bytes = 0
    sessions = set()
    for path in sorted(
        glob.glob(os.path.join(project_dir, ".claude", "ziptie", "logs", "*.jsonl"))
    ):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict):
                    continue
                if entry.get("session"):
                    sessions.add(entry["session"])
                if entry.get("decision") not in ("deny", "inject"):
                    continue
                deliveries += 1
                source = rule_doc.get(entry.get("rule", ""))
                delivered_bytes += doc_sizes.get(source, 0)
    return {
        "n_docs": len(doc_sizes),
        "import_bytes": sum(doc_sizes.values()),
        "body_bytes": body_bytes,
        "deliveries": deliveries,
        "delivered_bytes": delivered_bytes,
        # 하한: 무배달 세션은 로그에 흔적이 없다 (SessionStart 훅은 compact 전용)
        "sessions_seen": len(sessions),
    }


def main():
    result = summarize(os.getcwd())
    if not result["rules"] and not result["never_triggered"]:
        print("ziptie: 기록된 로그가 없다.")
        return
    print(f"{'룰':<24} {'배달(deny)':<10} {'주입(inject)':<12} {'통과':<6}")
    rearm_count = 0
    for name, c in sorted(result["rules"].items()):
        if name == "(compact)":
            rearm_count = c.get("rearm", 0)
            continue
        print(
            f"{name:<24} {c.get('deny', 0):<10} {c.get('inject', 0):<12} "
            f"{c.get('allow-after-delivery', 0):<6}"
        )
    for name in result["never_triggered"]:
        print(f"{name:<24} {'한 번도 트리거되지 않음 (죽은 룰?)'}")
    if rearm_count:
        print(f"컴팩션 재무장(rearm): {rearm_count}회")
    eco = context_economics(os.getcwd())
    if eco["n_docs"]:
        saved = eco["import_bytes"] - eco["body_bytes"]
        print(
            f"\n[컨텍스트 절약 추정] source 문서 {eco['n_docs']}개 "
            f"{eco['import_bytes']:,}B — @import했다면 매 세션 선불. "
            f"ziptie 방식 세션 시작 비용은 룰 본문 {eco['body_bytes']:,}B "
            f"(세션당 약 {saved:,}B 절약). "
            f"배달 지출 {eco['deliveries']}건 ≈ {eco['delivered_bytes']:,}B "
            f"(현재 문서 크기 기준 근사). "
            f"로그에 잡힌 세션 {eco['sessions_seen']}개 — 하한(무배달 세션은 "
            f"로그에 없음), 누적 절약은 최소 세션수×{saved:,}B − 배달 지출."
        )


if __name__ == "__main__":
    main()
