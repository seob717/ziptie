# 컴파일 벤치마크 파일럿 — 사전등록 (2026-07-10)

지금까지의 실험은 "배달이 준수를 지키는가"(런타임)를 쟀다. 이 파일럿은 축을 바꿔
"**컴파일러(/nunchi:compile 지침)가 야생의 CLAUDE.md를 얼마나 소화하는가**"(정적)를 잰다.
실행 전에 코퍼스 선정 규칙·지표·제외 규칙을 고정한다.

## 1. 질문

야생의 실전 CLAUDE.md를 입력했을 때,

- Q1. 문서에서 액션 결합 가능한 룰이 얼마나 추출되는가? (컴파일 가능률)
- Q2. 생성된 트리거가 형식적으로 유효하고, 가이드(content 룰의 `path:` 필수)를 지키며,
  무해한 표준 커맨드에 오탐하지 않는가? (트리거 품질)
- Q3. `block` 강도는 원문의 명시적 금지 표현이 있을 때만 부여되는가? (strength 판정 일관성)

## 2. 입력 코퍼스 (n=12, 실행 전 고정)

### 2.1 명명 코퍼스 5건 (2026-07-10 GitHub API로 실존 검증 완료)

| id | 원본 | 성격 |
|---|---|---|
| airflow | apache/airflow `CLAUDE.md` (~35KB) | 고밀도 규칙 |
| nextjs | vercel/next.js `CLAUDE.md` (~22KB) | 고밀도 규칙 |
| supabase | supabase/supabase `.claude/CLAUDE.md` | PR 체크리스트·마이그레이션 규칙 |
| langgraph | langchain-ai/langgraph `CLAUDE.md` (~1.9KB) | 소형·조건부 규칙 |
| cloudflare | cloudflare/workers-sdk `CLAUDE.md` (~132B) | **음성 대조군** (빈 스텁 — 룰 0개 기대) |

### 2.2 awesome-claude-md 표집 7건

[josix/awesome-claude-md](https://github.com/josix/awesome-claude-md)의 `scenarios/<카테고리>/<항목>/README.md`는
분석 문서이며 원본은 "CLAUDE.md: View Original" 링크가 가리킨다. 표집 규칙:

- 6개 카테고리(complex-projects, developer-tooling, getting-started,
  infrastructure-projects, libraries-frameworks, project-handoffs) 각각에서
  **알파벳순 첫 항목** 1건 + 최대 카테고리(developer-tooling)의 **두 번째 항목** 1건 = 7건.
- 항목 채택 조건: ① 항목 디렉터리에 README.md가 있고 View Original 링크가 있다,
  ② 링크의 원본 CLAUDE.md가 raw로 실존한다(HTTP 200), ③ 명명 코퍼스 5건과 중복이 아니다,
  ④ 크기 200B 이상이다. 조건 실패 시 같은 카테고리의 다음 알파벳 항목으로 넘어간다.
- 수집 시점에 실제 채택된 12건의 URL·크기·SHA256을 RESULTS 원장에 기록한다.
- 코퍼스 파일 자체는 재배포 라이선스가 불확실하므로(큐레이션 레포 SPDX NONE)
  **커밋하지 않는다** (`pilot/compile-bench/corpus/` gitignore). URL+SHA로 재현한다.

## 3. 처치 (컴파일 실행)

- 컴파일러 = `commands/compile.md`(v0.5.0, 커밋 392505d)의 §2~§4 지침을 그대로 프롬프트에
  포함한 서브에이전트 1개/문서. 모델은 **sonnet 고정** (선행 실험과 동일).
- 룰 파일을 실제로 쓰는 대신 동일 정보를 JSON으로 반환하게 한다 (스키마 §3.1).
  §5(파일 생성)·§6(사용자 리뷰)·§7(클로징)은 벤치마크 대상이 아니므로 제외한다.
- 문서당 1회 실행. 에이전트 오류·JSON 스키마 불일치 시 **1회 재시도** 후 실패면 제외(§5).

### 3.1 출력 스키마

```json
{
  "doc": "<id>",
  "rules": [
    {"name": "...", "tool": "Bash|Edit|Write", "pattern": "...",
     "field": null, "path": null, "strength": "block|require-read|inject",
     "evidence": "strength 판단 근거가 된 원문 인용 (짧게)"}
  ],
  "uncompilable": ["액션 결합 불가로 스킵한 규칙 요약", "..."]
}
```

## 4. 지표 (채점기 `pilot/grade_compile_bench.py`, stdlib 전용)

- **M1 컴파일 가능률** (문서별): `len(rules)`, `len(uncompilable)`,
  비율 `rules / (rules + uncompilable)`. 대조군(cloudflare)은 rules 0개 기대.
- **M2 트리거 형식 품질** (룰별 → 집계):
  - `re.compile(pattern)` 성공 (path 있으면 path도)
  - `tool ∈ {Bash, Edit, Write}`
  - **content 룰(`field` 지정)의 `path:` 동반률** — compile.md가 필수로 지시(392505d)
- **M3 오탐 스모크** (룰별 → 집계):
  - Bash 룰 pattern을 아래 **고정 무해 커맨드 10종**에 매칭 — 기대 매칭 0건:
    `git status` / `ls -la` / `npm test` / `git log --oneline` / `python -m pytest`
    / `git add .` / `gh pr view 12` / `git diff` / `echo hello` / `git checkout -b feat/x`
  - content 룰은 `docs/guide.md`·`README.md` 경로에 대해 path 조건이 매칭을 걸러내는지
    (path 없으면 자동 오탐 취급 — M2와 이중 계상 아님, 별도 행으로 보고)
- **M4 strength 판정**: 강도 분포 + `block` 룰 전수에 대해 evidence(원문 인용)를
  원본 문서와 대조해 명시적 금지 표현("never", "do not", "금지" 등 원문 표현) 실재 여부를
  **주 세션이 수기 확인**해 룰별 ✅/❌ 기록. evidence가 원문에 없는 인용이면 ❌.

## 5. 제외 규칙

- 원본 404·실존 실패 → §2.2 규칙으로 다음 항목 대체 (수집 단계에서 처리).
- 에이전트 재시도 후에도 JSON 스키마 불일치·오류 → 해당 문서 제외하고 사유 기록.
- 제외로 n<10이 되면 파일럿 중단하고 코퍼스 재설계.

## 6. 해석 한계 (실행 전에 못박음)

- 파일럿이며 게이트 없음 — 기술 통계와 정성 관찰만 보고한다.
- 모델 1종(sonnet)·문서당 1런이므로 분산 추정 불가. "컴파일 품질 우위" 같은 비교 주장 불가.
- M3은 고정 10종 커맨드에 대한 스모크일 뿐 실제 레포 히스토리 대조가 아니다.
  통과해도 "오탐 없음"이 아니라 "표준 커맨드에 안 걸림"까지만 주장한다.
- M4 수기 확인은 주관이 개입한다 — 판정 근거(원문 인용 위치)를 RESULTS에 전부 남긴다.
