# compile 벤치 재실행 — §4.5 저신뢰 확인 단계 무회귀 확인 (2026-07-16)

이슈 #35의 게이트 측정. `commands/compile.md`에 §4.5(저신뢰 판단을 룰 파일에 쓰기 전에
사용자 질문으로 승격 — 질문 상한 3, 고신뢰 비질문, 비대화 실행은 기존 동작 유지)를
추가하는 변경이 기존 추출 품질을 회귀시키지 않는지, 그리고 질문 남발 금지 게이트가
지켜지는지 확인한다.

## 방법

- 코퍼스: `pilot/compile-bench/manifest.json`의 12건 — skillroute 재실행
  (`RESULTS-compile-bench-skillroute.md`, 0716)과 동일한 로컬 사본을 양군에 동일 입력으로
  사용 (A/B 내부 비교 유효; airflow·nextjs의 0710 원장 대비 드리프트는 그 문서에 기록됨).
- 처치: 문서당 서브에이전트 1회, sonnet 고정 (DESIGN-compile-bench §3과 동일).
  - **A군(base)**: 현행 §2~§4 (main, 커밋 464a1fc) — 같은 날 대조군.
  - **B군(confirm)**: §2~§4 + 신규 §4.5. 벤치는 비대화 실행이므로 §4.5의 지침대로
    질문 없이 확정하되, **계측 전용**으로 출력 스키마에 `low_confidence`
    (flag된 판단: rule/category/reason)와 `questions`(대화형이었다면 물었을 ≤3개)를
    추가해 보고하게 했다.
- 채점: `grade_compile_bench.py`의 M1~M3 그대로 (3분류 스키마의
  `skill_candidates`+`always_on`은 스킵 합계로 환산). 출력:
  `compile-bench/outputs-confirm-base/`, `outputs-confirm/`.

## 결과

| 지표 | A(base) | B(confirm) |
|---|---|---|
| 룰 합계 | 126 | 128 (+1.6%) |
| 스킵 합계 | 164 | 138 |
| 컴파일 가능률 | 43% | 48% |
| 형식 유효 | 126/126 (100%) | 128/128 (100%) |
| 날조 (음성 대조군 cloudflare) | 0 | 0 |
| bash 오탐 | 2 | 2 |
| content 오탐 | 6 | 6 |
| 강도 분포 | block 51 · require-read 47 · inject 28 | block 58 · require-read 50 · inject 20 |

- bash 오탐 2건은 양군 **동일 계열**(airflow 호스트 pytest 앵커 `^(pytest|python|airflow)\b`,
  nextjs checkout 후 재빌드) — 0710 원측정·skillroute 재실행에서도 나온 base 스펙 자체의
  기존 계열이다.
- content 오탐 6건(3쌍)도 양군 동일 계열: airflow "Dag title-case"/"약어 미풀이" 쌍과
  nextjs 문서 highlight 줄번호 쌍 — md/rst를 **정당하게 겨냥한 문서 콘텐츠 룰**로,
  M3 휴리스틱의 고정 가정에 걸린 것(skillroute 측정에서 과추출 아님으로 판정한 것과
  같은 부류).
- 문서별 룰 수는 단일 런 분산이 크다(같은 base 계열 스펙으로 0716 skillroute 143 →
  이번 A군 126). 게이트 판정은 사전 방식대로 양군 합계·오탐 계열 대조로 한다.

### §4.5 계측 (B군)

- flag 46건 / 룰 128건, 질문(대화형 가정) 25건 — **문서당 최대 3, 상한(≤3) 위반 0**.
- 카테고리 분포: trigger 33 · strength 10 · routing 3 — 사전 등록한 저신뢰 패턴 중
  "문서에 도구가 명시되지 않은 트리거 추론"이 최다. 실제 flag 예: BPlusTree3는 문서에
  `git`이라는 단어가 한 번도 없는데 커밋 규칙 3건을 `git commit`에 바인딩했음을 스스로
  flag했고, langgraph는 PR 생성 도구 미언급 상태의 `gh pr create` 추론 1건만 flag했다.
- **음성 대조군 cloudflare: flag 0 · 질문 0.** 룰 0건 문서(microfolio)도 flag 0.
- 고신뢰 비질문 스팟 확인: 명시적 금지 문구("Never …")에서 온 block 판정은 flag되지
  않았다(langgraph의 block 2건 등) — "고신뢰 판단에 질문하지 않는다" 지침과 정합.

### 게이트 판정

- **recall 무회귀 — 통과**: 룰 합계 126 → 128 (+1.6%).
- **과추출·포맷·날조 무회귀 — 통과**: 형식 유효 100%/100%, 날조 0/0, bash·content 오탐
  모두 동수·동일 계열.
- **질문 남발 금지 — 통과**: 전 문서 질문 ≤3, 고신뢰 판단 비플래그 스팟 확인,
  비대화 실행에서 질문 0(계측 보고로만 대체).

## 한계

- 단일 런·모델 1종(sonnet)이라 분산 추정 불가 — 문서별 수치가 아니라 합계·계열 대조로만
  판정했다.
- flag의 **정밀도는 미측정**: flag된 판단이 실제 골드 오판과 얼마나 겹치는지는 이번에
  재지 않았다(질문 내용의 타당성은 수기 검토만 — 전량 기록은 출력 JSON에 있음).
- 계측 프롬프트는 실제 대화형 질문 UX와 다르다("묻지 않고 보고"). 대화형에서의 질문
  체감 품질은 별도 관찰 대상.
