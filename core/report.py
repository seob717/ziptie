"""nunchi 로그 집계 — 룰별 배달/통과 횟수와 죽은 룰 목록."""

import glob
import json
import os

from core.rules import load_rules


def summarize(project_dir: str) -> dict:
    counts = {}
    for path in sorted(
        glob.glob(os.path.join(project_dir, ".claude", "nunchi", "logs", "*.jsonl"))
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


def recompile_candidates(project_dir: str) -> list:
    """source 문서가 룰 파일보다 최신인 룰 — 재컴파일 후보 (#17).

    mtime 휴리스틱이라 후보는 "확인하라"는 신호일 뿐이다: 내용 보강이면
    재컴파일이 필요 없고(배달이 원본을 매번 읽음), 문서 변경 없이 도구가
    바뀌는 트리거 드리프트는 여기 안 잡힌다(죽은 룰 통계가 보완).
    반환: [(source 경로, [룰 이름들])] — source 기준 정렬.
    """
    candidates = {}
    for rule in load_rules(project_dir):
        if not rule.source:
            continue
        try:
            newer = os.path.getmtime(
                os.path.join(project_dir, rule.source)
            ) > os.path.getmtime(rule.path)
        except OSError:
            continue  # source 부재 등 — 배달 폴백과 같은 태도로 조용히 건너뜀
        if newer:
            candidates.setdefault(rule.source, []).append(rule.name)
    return sorted(candidates.items())


def context_economics(project_dir: str) -> dict:
    """@import 대비 컨텍스트 절약 추정 (PROBE-context-economics 방법의 레포별 산수).

    - import_bytes: 룰들이 참조하는 source 문서의 합계(중복 제거) —
      이 문서들을 CLAUDE.md에서 @import했다면 매 세션 시작에 실렸을 양.
    - body_bytes: 룰 본문 합계 — nunchi 방식에서 세션 시작에 실리는 양.
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
    sessions, tracked = set(), set()
    for path in sorted(
        glob.glob(os.path.join(project_dir, ".claude", "nunchi", "logs", "*.jsonl"))
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
                    if entry.get("decision") == "session-start":
                        tracked.add(entry["session"])
                if entry.get("decision") not in ("deny", "inject"):
                    continue
                if str(entry.get("rule", "")).startswith("("):
                    continue  # (recompile) 등 메타 항목 — 룰 배달 지출이 아니다
                deliveries += 1
                source = rule_doc.get(entry.get("rule", ""))
                delivered_bytes += doc_sizes.get(source, 0)
    return {
        "n_docs": len(doc_sizes),
        "import_bytes": sum(doc_sizes.values()),
        "body_bytes": body_bytes,
        "deliveries": deliveries,
        "delivered_bytes": delivered_bytes,
        # InstructionsLoaded 훅(#10)이 세션마다 session-start 1줄을 남기므로
        # 훅 도입 이후 세션은 전수 관측된다. 도입 전 로그는 배달 흔적만 있어 하한.
        "sessions_seen": len(sessions),
        "sessions_tracked": len(tracked),
    }


def main():
    result = summarize(os.getcwd())
    if not result["rules"] and not result["never_triggered"]:
        print("nunchi: 기록된 로그가 없다.")
        return
    print(f"{'룰':<24} {'배달(deny)':<10} {'주입(inject)':<12} {'통과':<6}")
    rearm_count = 0
    for name, c in sorted(result["rules"].items()):
        if name == "(compact)":
            rearm_count = c.get("rearm", 0)
            continue
        if name in ("(session)", "(recompile)"):
            continue  # 메타 항목 — 룰 행이 아니다 (세션 관측·재컴파일 안내)
        print(
            f"{name:<24} {c.get('deny', 0):<10} {c.get('inject', 0):<12} "
            f"{c.get('allow-after-delivery', 0):<6}"
        )
    for name in result["never_triggered"]:
        print(f"{name:<24} {'한 번도 트리거되지 않음 (죽은 룰?)'}")
    for source, names in recompile_candidates(os.getcwd()):
        print(
            f"재컴파일 후보: {source} (룰 {', '.join(names)}) — source가 룰 파일보다 "
            f"최신. 규칙 신설·트리거·강도 변경이었다면 /nunchi:compile {source}"
        )
    if rearm_count:
        print(f"컴팩션 재무장(rearm): {rearm_count}회")
    eco = context_economics(os.getcwd())
    if eco["n_docs"]:
        saved = eco["import_bytes"] - eco["body_bytes"]
        if eco["sessions_tracked"]:
            session_note = (
                f"로그에 잡힌 세션 {eco['sessions_seen']}개 "
                f"(InstructionsLoaded 훅 전수 관측 {eco['sessions_tracked']}개 포함 — "
                f"훅 도입 후 세션은 빠짐없이 집계), "
                f"누적 절약 ≈ 세션수×{saved:,}B − 배달 지출."
            )
        else:
            session_note = (
                f"로그에 잡힌 세션 {eco['sessions_seen']}개 — 하한(무배달 세션은 "
                f"로그에 없음), 누적 절약은 최소 세션수×{saved:,}B − 배달 지출."
            )
        print(
            f"\n[컨텍스트 절약 추정] source 문서 {eco['n_docs']}개 "
            f"{eco['import_bytes']:,}B — @import했다면 매 세션 선불. "
            f"nunchi 방식 세션 시작 비용은 룰 본문 {eco['body_bytes']:,}B "
            f"(세션당 약 {saved:,}B 절약). "
            f"배달 지출 {eco['deliveries']}건 ≈ {eco['delivered_bytes']:,}B "
            f"(현재 문서 크기 기준 근사). " + session_note
        )


if __name__ == "__main__":
    main()
