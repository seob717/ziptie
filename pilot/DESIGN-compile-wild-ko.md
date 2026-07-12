# 야생 한국어 CLAUDE.md 컴파일 측정 — 사전등록 (2026-07-12, 이슈 #15)

#13 다국어 측정은 **번역 코퍼스**였다 — 코드 토큰 보존·검수를 거친, 야생보다 쉬운
조건(RESULTS-compile-multilingual §6). 이 실험은 실제 저장소에서 표집한 **야생
한국어 CLAUDE.md**로 같은 파이프라인(gold → 컴파일 → 매칭 → 채점)을 돌려 그
일반화 공백을 메운다. 관찰 파일럿이며 게이트 없음 — 기술 통계와 실패 패턴만
보고하고 우열 주장을 하지 않는다. 실행 전에 이 문서를 커밋으로 동결한다.

## 1. 질문

- Q1. 야생 한국어 문서에서 recall·형식 품질·과추출이 번역 코퍼스 실측과 다른가?
- Q2. strength 판정(§4 화행 개정, f95ee7e)이 야생 한국어 강도 표현에서도 작동하는가?
- Q3. 야생 특유의 실패 유형(혼합 언어, 비정형 구조, 존댓말/반말 혼용 등)이 있는가?

## 2. 표집 프로토콜 (결정적, 실행 전 고정)

- **고정 쿼리 3종** (GitHub code search, `gh search code --filename CLAUDE.md`,
  limit 30/쿼리, 표집 시각 1회 실행): ① `"하지 마세요"` ② `"해야 합니다"` ③ `"금지"`.
  세 결과의 합집합이 후보군. 원시 결과는 원장으로 보존한다.
- **기계 필터**: ⓐ 파일명이 정확히 `CLAUDE.md`, ⓑ 원문 2KB~60KB,
  ⓒ 코드펜스 밖 텍스트에서 한글 문자 ≥ 300자 그리고 한글/(한글+로마자) ≥ 0.3,
  ⓓ 내용 SHA256 중복 제거, ⓔ seob717 소유·포크 제외.
- **수기 제외(사유 기록 의무)**: 실제 소프트웨어 프로젝트의 지침이 아닌 것 —
  템플릿·모음집·강의 자료·프롬프트 실험장. 제외 사유는 manifest에 남긴다.
- **선정**: 필터 통과 후보를 저장소 별점 내림차순(동점은 nameWithOwner 오름차순)으로
  정렬해 **상위 4건**. 적합 문서가 3건 미만이면 실험 중단하고 재설계.
- **동결**: 선정 4건은 기본 브랜치 HEAD 커밋에 핀한 raw URL + SHA256을
  `pilot/compile-wild/manifest.json`으로 커밋. 코퍼스 파일 자체는 비커밋
  (`pilot/compile-wild/corpus/` gitignore) — 라이선스 원칙은 #11~#13과 동일하며,
  원장에는 짧은 인용(evidence)만 담는다.

## 3. gold 구축 — recall 실험 A1 프로토콜 재사용

`DESIGN-compile-recall.md` §3·§7(A1) 그대로: **Codex(GPT 계열)가 문서당 새 세션**,
레포 밖 격리 디렉터리(문서 1건 + 정답 스키마 + `commands/compile.md` §2·§4 발췌만),
네트워크 차단, 컴파일 출력 비노출. 차이 1가지만 명시:

- evidence 인용은 **한국어 원문에서** 그대로 딴다 (recall 실험은 영어 원문).
- §4 발췌는 현행 개정본(f95ee7e) — gold의 기대 strength와 컴파일러가 같은 지침을
  본다. 이것은 의도된 설계다(측정 대상이 "지침이 야생 한국어에 작동하는가"이므로).

완료 시 `pilot/compile-wild/gold/<id>.json` 커밋으로 동결. 컴파일은 동결 이후 시작.

## 4. 컴파일·매칭 — #15 v2 파이프라인 재사용

- **컴파일**: sonnet 서브에이전트 문서당 1개, 같은 배치.
  `compile-multilingual/templates/PROMPT-compile-v2.md` 치환본 그대로.
  출력 저장 시 스키마·정규식 검증(불일치 시 같은 프롬프트로 1회 재시도).
- **매칭**: Codex 문서당 새 세션, `templates/PROMPT-match-wild.md` —
  PROMPT-match.md와 동일하되 "gold는 영어" 문구를 "gold와 문서가 같은 언어(한국어)일
  수 있다"로 바꾼 것 하나만 차이. 무결성 규칙(전수 판정·1:1·gold 동결·amendments
  기록만 허용) 동일.
- 저장: `pilot/compile-wild/outputs/`, `matches/`. 집계는
  `pilot/grade_compile_wild.py`(stdlib) — multilingual 집계기의 M1/M2/M4/M5 +
  evidence 대조를 gold-dir 파라미터화해 재사용.

## 5. 지표·보고 (게이트 없음)

- M1 recall(문서별), 미스 category 분포, unmatched class 분포(M4), M2 형식,
  M5 strength(gold 기대 대비) + evidence 실재 대조.
- **참고 비교만**: 번역 코퍼스 ko 셀(#13/#15)과 영어 recall v2 수치를 옆에 놓되,
  코퍼스가 다르므로 직접 비교 불가를 명시한다.
- 산출물: `RESULTS-compile-wild-ko.md` (§0 실행 기록·이탈 포함).

## 6. 한계 (실행 전 못박음)

- n=4, 문서당 1런, gold 작성자 = 매칭 판정자와 같은 모델 계열(Codex, 세션 분리) —
  recall 실험 A1과 같은 한계. 표본이 "별점 상위"로 치우친다(잘 관리된 레포 편향).
- GitHub 코드 검색은 재현 불가(색인 변동) — 표집의 결정성은 "고정 쿼리 + 기록된
  후보군 + 기계 필터 + 정렬 규칙"까지고, 재실행 시 같은 후보군을 보장하지 않는다.
  선정 결과는 manifest 동결로 재현성을 확보한다.
- 야생 문서는 gold의 완전성 검증이 더 어렵다(비정형 구조) — recall은 "Codex 정답
  대비" 상한/하한 불명 추정으로만 해석한다.
