# 다국어 컴파일 호환성 — 결과 (2026-07-12, 이슈 #13)

사전등록: `DESIGN-compile-multilingual.md`(da4dd51). 프롬프트 4종 템플릿 커밋 고정본 사용.
번역·검수·매칭 = Codex(codex-0.144.1, GPT-5) 셀당 새 세션, 컴파일 = sonnet 서브에이전트
셀당 1개(같은 배치). gold = 93da52e 고정본(변경 없음 확인). 코퍼스·번역본은 비커밋 —
SHA256은 `compile-multilingual/translation-shas.txt`, 원본은 compile-bench manifest.

**한 줄 요약**: 문서 내 영어↔번역 쌍 recall 차이는 −2~+3룰(중복 판정 불일치 0 실측),
형식 위반 0, over-extraction 0. 이 파일럿 조건(번역 코퍼스, 문서당 1런)에서 언어 축의
큰 열화는 관찰되지 않았다. 단, 번역 강도 표현에서 실패 1셀(supabase.ko)과 강화 1건
(langgraph.ja)이 나왔다 — 언어 축의 실질 리스크는 recall이 아니라 **strength**였다.

## 0. 실행 기록·프로토콜 이탈

- 번역 12셀 전부 기계 검증(백틱 스팬·코드블록 다중집합 보존) 통과.
- **supabase.ko = 번역 실패 셀(ITT)**: 의미 보존 검수에서 g21("Avoid barrel re-export
  files")이 "사용하지 마세요"로 강화 판정 → 사전등록대로 전문 재번역 1회 →
  재번역본("사용하지 않습니다")도 독립 세션이 같은 판정 → 컴파일하지 않고 실패로 집계.
  그 외 11셀은 gold 룰 단위 보존 전수 통과(nextjs 57룰 × 3언어 포함).
- microfolio(음성 대조군)는 검수 통과(규칙성 문장 추가/삭제 0), 단 §4 참조.
- 컴파일 출력 처리: 일부 에이전트가 JSON을 마크다운 펜스로 감싸 반환 — 내용 스키마는
  전부 유효해 펜스만 제거하고 채택(재시도 0회 발동). 전송 계층에서 HTML 이스케이프된
  `&lt;` 등은 저장 시 복원. 저장 시 전 룰 정규식 컴파일·어휘 검증 통과.
- 매칭 13세션(11셀 + 중복 2) 전부 무결성 검사 통과(gold 전수 판정·1:1·gold 동결).

## 1. M1 — recall (matches/gold, 고정 gold 93da52e)

| doc | en | ko | ja | es | (L−en) ko/ja/es |
|---|---|---|---|---|---|
| langgraph | 2/6 | 2/6 | 2/6 | 2/6 | +0 / +0 / +0 |
| supabase | 5/22 | **번역 실패** | 5/22 | 6/22 | — / +0 / +1 |
| nextjs | 26/57 | 26/57 | 24/57 | 29/57 | +0 / −2 / +3 |
| (참고: 마이크로 합계) | 33/85 | 28/85¹ | 31/85 | 37/85 | |

¹ ITT: supabase.ko 실패 = 0/22로 포함. nextjs가 gold의 67%를 차지하므로 마이크로
합계는 참고만(사전등록 §2).

- **중복 판정 불일치율: 0%** — 사전 지정 2셀(langgraph.ko, nextjs.es)을 독립 세션이
  재판정한 결과 matches의 gold_id 집합·unmatched 분류가 완전 일치. 이번 배치의 판정
  드리프트 눈금이 0이므로, 위 ±3룰 차이는 판정 노이즈보다는 컴파일 비결정성·언어
  효과로 보는 게 자연스럽다(단 컴파일 런간 분산은 비반복이라 분리 불가, §6).
- 추출량 자체는 언어별로 흔들렸다(nextjs: en 28 / ko 32 / ja 28 / es 34룰) —
  그런데 recall은 비슷하다. 초과 추출분은 대부분 gold-miss(실재 룰) 또는 분할 차이.

## 2. M2 — 형식 품질

**전 15셀 위반 0/룰.** 정규식 컴파일 실패 0, tool 어휘 밖 0, field-있는데-path-없음 0.
비영어 문서에서도 트리거는 전부 영문 정규식·코드 토큰으로 산출됐다(문서의 코드
토큰이 원문 보존된 덕 — 번역 프로토콜의 효과).

## 3. M3 — 오탐 스모크 (무해 커맨드 10종 + content 경로 2종)

사전 고정 정탐 2쌍 중 ②("브랜치 전환 후 재빌드" 의도 × `git checkout -b feat/x`)가
전 4언어에서 발동 — 정탐 제외. ①(호스트 pytest 금지 의도)은 해당 룰 미추출로 미발동.
**그 외 매칭은 사전등록상 전부 위반으로 계상**:

| cell | 위반 | 내역 |
|---|---|---|
| nextjs.en | 1 | docs-highlight × `docs/guide.md` |
| nextjs.ko | 2 | save-api(`\b(gh|curl)\b`) × `gh pr view 12`, docs-highlight × `docs/guide.md` |
| nextjs.ja | 2 | 위와 동형 |
| nextjs.es | 5 | save-api × `gh pr view 12`, pr-status-script × `gh pr view 12`, git-add-secret × `git add .`, docs-highlight × `docs/guide.md`·`README.md` |
| 나머지 11셀 | 0 | |

판독 노트(계상은 위 그대로): docs-highlight는 docs 마크다운을 겨냥한 룰이라
`docs/guide.md` 발동이 의도된 동작에 가깝다(4언어 공통 — 언어 효과 아님, 벤치 무해
목록의 한계). 언어 실질 차이는 ② `\b(gh|curl)\b`형 광역 트리거가 en에는 없고
ko/ja/es에 나타난 것, ③ es가 `git add .`·`README.md`까지 잡는 광역 스코프 2건을
추가로 만든 것. es가 가장 공격적으로 추출(34룰)하면서 트리거 정밀도를 조금 잃었다.
en의 동일 의도 룰(never-commit-env-secrets)은 `\.env(?!\.example)`로 스코프했다.

## 4. M4 — 날조·음성 대조군

- **over-extraction: 판정 11셀 전부 0.** duplicate 2(nextjs.ko/es 각 1), gold-miss는
  nextjs에서 언어당 2~5건(gold가 안 담은 실재 룰 — 기록만, gold 동결).
- **microfolio(자연어 음성 대조군, 기대 0룰): en 1 / ko 0 / ja 1 / es 3.** 날조는
  아니다 — 전부 문서에 실재하는 서술(프로젝트 frontmatter YAML 스키마, `Ak` 접두
  명명 관례)을 룰로 승격한 것. 그러나 이 문서는 의무 표현이 없는 순수 서술문이라
  기대는 0이었다. en에서도 1룰이 나온 점, 그리고 compile-bench 당시 en 실행은
  0룰이었던 점에서 **런간 비결정성이 언어 효과보다 크다**. es만 3룰(명명 관례까지
  승격)로 승격 경향이 가장 강했다 — §3의 es 광역화와 방향이 같다.

## 5. M5 — strength 정확도·evidence

gold 기대 strength 대비, 매치된 룰의 confusion(미스는 M1에 계상, 여기선 제외 수만 표기):

| cell | 일치 | 지배적 불일치 |
|---|---|---|
| langgraph en/ko/ja/es | 1/2 · 1/2 · **2/2** · 1/2 | block→require-read(en·es), block→inject(ko) |
| supabase en/ja/es | 3/5 · 2/5 · 4/6 | block→require-read 각 1 + 강도 하향/상향 혼재 |
| nextjs en/ko/ja/es | 16/26 · 17/26 · 15/24 · 17/29 | **block→require-read 6~9건** (전 언어 공통) |

- 지배적 패턴은 **전 언어 동일**: gold가 명시적 금지("Never/절대")로 본 룰에 컴파일러가
  require-read를 부여. 언어 효과가 아니라 컴파일러의 보수적 strength 판정 성향.
- **언어 고유 사례 1건**: langgraph.ja만 double-backtick 룰에 block을 부여해 gold와
  일치(2/2). 원인은 번역 자체 — "Do NOT use"가 "絶対に使用しないでください"로
  강화됐고 검수를 통과했다. supabase.ko의 실패("avoid"의 한국어 강도)와 합치면,
  **언어 축의 실측 리스크는 recall이 아니라 강도 표현의 번역 비등가성**이다.
- evidence 기계 대조(공백 정규화): 매치 룰 중 29건 미일치 플래그 → 수기 판독 결과
  **전부 근사 인용, 날조 0**. 유형: 줄 경계·코드펜스 이어붙임(예: "…branches:" +
  `git checkout <branch>`), 마크다운 장식 탈락(굵게·백틱 래퍼), 접두 절 생략
  ("Default agent rule: " 등), 인접 불릿 2개 축약 결합 1건(nextjs.en
  match-ci-env-vars). 이전 실행들과 같은 패턴.

## 6. 해석·한계

- **Q1(탐색)**: 이 조건에서 recall의 언어 간 차이는 문서당 −2~+3룰. 판정 드리프트
  실측 0이므로 차이의 출처는 컴파일 비결정성 ∪ 언어 효과이고 이 설계로는 분리
  불가(문서당 1런). "언어 호환성이 같다"는 주장은 하지 않는다(사전등록).
- **Q2**: 형식 품질 언어 차이 없음(전부 0). **Q3**: strength 불일치는 전 언어 공통
  패턴 + 번역 유래 1건. **Q4**: 날조 0, 단 서술문 승격이 en 포함 3언어에서 발생.
- 번역 코퍼스는 야생 비영어 문서보다 쉬운 조건이다 — 야생 한국어 CLAUDE.md 일반화
  불가(사전등록 §6). 번역·검수·판정 모두 GPT 계열 1종.
- **실행에서 얻은 부수 발견 2건**: ① 영어 화행 "avoid"(권고)의 한국어 자연 번역이
  검수자 눈에는 무조건 금지로 읽힌다 — 2회 연속. 한국어 CLAUDE.md 작성 가이드에
  "권고는 '~을 피하는 게 좋다'처럼 명시적으로" 같은 지침 소재. ② 컴파일러의
  block 부여가 원문 강도 표현의 언어별 뉘앙스에 민감하다(ja 사례).
- 후속 소재: 야생 비영어 CLAUDE.md 표집(이슈 #13 원안), strength 판정 지침의
  비영어 금지 표현 예시 보강.
