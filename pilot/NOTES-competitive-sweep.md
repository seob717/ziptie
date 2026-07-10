# 경쟁 스윕 노트 — "CLAUDE.md → 트리거 결합 훅 컴파일" 카테고리 (2026-07-10)

README 비교표의 5종(hookify·Ruler·rulesync·Writ·네이티브 rules) **외에** 같은 메커니즘의
도구가 존재하는지 스윕한 기록. 결과가 "없다"여서, 판정 근거와 탐색 경로를 남긴다.
(스타 수·버전은 2026-07-10 기준 — 시간이 지나면 재확인할 것.)

## 판정

**ziptie의 메커니즘(규칙을 트리거에 컴파일해 도구 호출 시점에 JIT 배달 + 배달 상태 +
컴팩션 재무장)을 그대로 수행하는 서드파티 도구는 확인되지 않았다.**

## 인접 도구 지도

| 도구 | 규모 | 메커니즘 | ziptie와의 거리 |
|---|---|---|---|
| agentihooks | 스타 0 | 라이프사이클 훅으로 규칙 재주입(고정 간격), 원샷 배달 | 가장 근접하나 트리거 결합 컴파일 아님 |
| claude-code-agents-md | 스타 5 | 가장 가까운 AGENTS.md를 세션당 1회 통째 주입 | 파일 주입, 규칙 분해 없음 |
| cc-discipline (npm) | v2.11 | 사전 제작 규칙셋 + 하드코딩 가드 훅 번들 | 컴파일러 아님 |
| claude-md-optimizer | 스타 19 | CLAUDE.md를 progressive disclosure로 정적 재작성하는 스킬 | 같은 문제(토큰 비대)·다른 수단 — 문제 실재의 방증 |
| context-mode | 스타 18.8k | 훅으로 툴 출력 라우팅·감축 (규칙 아님) | 프레이밍만 겹침 — 포지셔닝 문구에서 혼동 주의 |
| cchook / superego / rule-porter | 소규모 | 훅 설정 DSL / 메타인지 평가 / Cursor 규칙 포맷 변환 | 다른 카테고리 |

## 실질 경쟁자 = 네이티브 기능의 확장

- path-scoped rules(2.0.64+)가 "경로별 규칙 로드" 워크어라운드를 흡수했다. 단 트리거는
  **파일 읽기 기반 경로 매칭뿐** — 액션(명령) 트리거·편집 내용 트리거·강제력·재무장은 없음.
- 신규 파일 Write 시 path-scoped rule 미로드 이슈(anthropics/claude-code#38487) —
  ziptie의 `trigger.tool: Write`가 커버하는 지점.
- **InstructionsLoaded 훅**(신규): 규칙/CLAUDE.md가 컨텍스트에 로드될 때 발화.
  로드맵 후보 — 모든 세션에서 발화하므로 `/ziptie:report`의 세션 수 하한 문제
  (무배달 세션은 로그에 흔적 없음)를 정확한 세션 카운트로 풀 수 있다.

## 스윕 주장 중 우리 실측과 충돌하는 것 (우리 실측이 우선)

스윕은 "PreToolUse additionalContext 미지원/버그"(이슈 #15345 등)라고 요약했으나,
**PROBE-inject.md에서 CLI 2.1.206 기준 additionalContext 주입이 동작함을 실측 확인**했고
inject 강도가 그 위에서 운용 중이다. 열린 이슈는 당시 버전 재현 실패로 기록돼 있다.

## 탐색 경로 (재현용)

WebSearch 8회(컴파일/JIT/lazy-loading/cursor 이식 쿼리), GitHub repo·code 검색
(`PreToolUse additionalContext CLAUDE.md rules` 등), npm·PyPI 검색,
awesome-claude-code 훅 섹션 전수. 한계: Reddit 인덱싱 빈약, 신생 스코프 npm 누락 가능.

## 포지셔닝 결론

- "유일하다" 류 문구는 쓰지 않는다 — 무명 도구까지 부정하는 주장은 반박에 취약.
  README는 지금처럼 기능 매트릭스와 실측으로만 말한다.
- 지속 우위는 기능 자체보다 **측정 문화(사전등록 실측)와 운영 기능(배달 상태·리포트·
  컨텍스트 경제성)**에 있다 — 네이티브가 액션 트리거를 내장하는 시나리오에 대한 대비.
