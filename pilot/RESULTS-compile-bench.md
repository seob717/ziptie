# 컴파일 벤치마크 파일럿 결과 (DESIGN-compile-bench.md 기준)

실행일: 2026-07-10. 컴파일 에이전트 12개(sonnet 고정), 지침 = commands/compile.md §2~§4
(커밋 392505d — `path:` 필수·git 글로벌 옵션 가이드 포함). 채점기 = 9a0c7c4.
코퍼스 12건의 URL·크기·SHA256은 `pilot/compile-bench/manifest.json` 원장 참조.

## 수집 노트 (§2 집행 기록)

- 표집 중 §2.2 조건 실패 4건은 규칙대로 다음 알파벳 항목으로 대체 (manifest `log` 참조:
  View Original 링크 없음 2, 원본 404 2, 명명 중복 1).
- **airflow·next.js의 CLAUDE.md는 AGENTS.md로의 심링크**였다 — raw가 대상 경로 문자열만
  반환해 실체(AGENTS.md)를 수집하고 manifest에 기록. 야생 수집 파이프라인을 만든다면
  심링크 처리(9B짜리 "본문" 필터)가 필수라는 부수 발견.
- 12건 전원 스키마 유효 — §5 제외 0건, 재시도 0건.

## M1 — 컴파일 가능률

| doc | 룰 | 불가 | 가능률 |
|---|---|---|---|
| airflow | 29 | 18 | 62% |
| nextjs | 27 | 21 | 56% |
| awm-developer-1 (HA-Irrigation) | 7 | 10 | 41% |
| awm-infrastructure-1 (dymension) | 7 | 4 | 64% |
| supabase | 4 | 3 | 57% |
| awm-libraries-1 (CKBoost) | 4 | 7 | 36% |
| awm-complex-1 (whereami) | 3 | 7 | 30% |
| awm-project-1 (BPlusTree3) | 3 | 7 | 30% |
| awm-developer-2 (claudecode.nvim) | 2 | 6 | 25% |
| langgraph | 2 | 2 | 50% |
| awm-getting-1 (microfolio) | 0 | 0 | — (순수 서술형) |
| cloudflare (음성 대조군) | 0 | 0 | — (기대대로 0) |
| **합계** | **88** | **85** | **51%** |

관찰: ① 음성 대조군에서 룰을 지어내지 않았다(0건). ② microfolio처럼 명령형 문장이
없는 순수 아키텍처 서술 문서는 0/0 — 야생 CLAUDE.md에는 "규칙 없는 문서"가 실재한다.
③ 가능률 ~51%는 "야생 규칙의 절반은 특정 액션에 못 묶는 상시 가이드"라는 뜻 —
액션 결합 JIT(ziptie)와 상시 컨텍스트(네이티브 로더·CLAUDE.md)의 **병행 설계 근거**.

## M2 — 트리거 형식 품질: 88/88 (100%)

- 정규식 컴파일 성공 88/88 (pattern·path 모두), tool 유효 88/88 (Bash 37 · Edit 43 · Write 8)
- **content 룰(field 지정) 28건 전원 `path:` 동반 (28/28)** — 392505d 가이드가 야생
  문서에서도 그대로 이행됨. 오늘 실사용 레포에서 실증된 오탐 패턴이 신규 컴파일에선
  구조적으로 차단된다.

## M3 — 오탐 스모크: 자동 집계 3건 → 수기 판독 결과 전부 지표 아티팩트

| 룰 | 자동 판정 | 수기 판독 |
|---|---|---|
| airflow / no-direct-host-commands (`^(pytest\|python\|airflow)\b`) | `python -m pytest`에 매칭 | **정탐** — 원문 규칙이 "호스트에서 pytest/python 직접 실행 금지, breeze 사용"이라 걸리는 게 목적 그 자체 |
| nextjs / bootstrap-build-after-branch-switch | `git checkout -b feat/x`에 매칭 | **경계 사례** — "브랜치 전환 후 빌드" 리마인더이며 신규 브랜치 생성도 전환에 포함. 의도 부합 |
| nextjs / docs-highlight-line-count (path `^docs/.*\.(md\|mdx)$`) | `docs/guide.md`에 발화 가능 | **정탐** — 마크다운 문서가 규칙의 표적. path가 정확히 그렇게 좁혀져 있음 |

사전등록 §6 한계 그대로: 고정 무해 커맨드 세트는 프로젝트 인지가 없어 "그 프로젝트에선
금지인 표준 커맨드"와 충돌한다. **진짜 트리거 결함(무관 커맨드 오폭)은 0건.**

## M4 — strength 판정: block 8/8 evidence 원문 실재

- 강도 분포: block 8 · require-read 61 · inject 19. **block은 airflow에서만** 나왔고
  전부 원문의 명시적 금지("Never run …", "NEVER add Co-Authored-By …", "MUST NOT …")와
  1:1 대응. 6건은 리터럴 일치, 2건은 원문 507행 "**Never**" 불릿 리스트의 항목을
  평탄화한 인용(509~510행 실재 확인).
- 명시 금지 없는 문서에 block을 남발한 사례 없음 — §4 강도 규칙("절대 금지"만 block)이
  야생 문서에서도 지켜졌다.

## 종합

야생 CLAUDE.md 12건(166KB)에 대해: 추출 88룰 **형식 유효 100%, content 룰 path 동반
100%, 트리거 결함 0, block 남발 0, 대조군 오염 0**. 파일럿 범위에서 컴파일러의 실패
모드는 관찰되지 않았고, 실패 모드 후보는 컴파일러가 아니라 지표 쪽(프로젝트 인지 없는
무해 커맨드 세트)에서 나왔다.

## 한계 (사전등록 §6 재확인)

- 모델 1종(sonnet)·문서당 1런 — 분산·재현성 미측정.
- **recall 미측정**: "문서에 있는데 추출을 놓친 룰"은 이 설계로 잡히지 않는다
  (M1은 자기신고 기반). 후속에서 문서별 정답 룰셋을 수기 구축해야 측정 가능.
- M3 스모크는 표준 커맨드 10종 한정 — 실제 레포 히스토리 대조가 아니다.
- README에 쓸 수 있는 문장은 "야생 CLAUDE.md 12건 파일럿에서 형식 결함 0"까지.
  "컴파일 품질 우위" 같은 비교 주장은 불가.

## 원장

- 코퍼스: `pilot/compile-bench/corpus/` (로컬, gitignore — 재배포 라이선스 불확실),
  재현은 `manifest.json`의 URL+SHA256으로.
- 컴파일 출력: `pilot/compile-bench/outputs/*.json` (커밋됨 — 룰 패턴과 짧은 인용만 포함)
- 실행 창: 2026-07-10 16:35~16:45 (에이전트 12개 병렬, 전원 1회 시도 성공)
