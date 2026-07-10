# inject 실현성 프로브 — PreToolUse additionalContext 실측

실행일: 2026-07-10. 환경: Claude Code CLI v2.1.206, macOS, 모델 sonnet, `claude -p --settings <파일>` 헤드리스. 목적: 로드맵의 `inject` 강도(차단 없는 JIT 배달)가 네이티브 프리미티브로 실현 가능한지 — 스펙(v2.1.9+)에는 있으나 주입 실패 버그 리포트(#19432, #20062, #55889)가 있어 실측이 필요했다.

## 방법

샌드박스에 PreToolUse(matcher: Bash) 훅을 설정하고, 훅이 `hookSpecificOutput.additionalContext`로 마커 문자열 + "답변 마지막 줄은 정확히 'PROBE-OK'" 규칙을 반환하게 했다. 헤드리스로 `ls` 실행을 시키고 (a) 주입 텍스트가 모델에게 보이는지, (b) 지시를 스스로 따르는지(무언급 행동 준수)를 관측.

## 결과

| 변형 | permissionDecision | 프레이밍 | 준수 | 비고 |
|---|---|---|---|---|
| 가시성 확인 | allow | 마커만 | 1/1 인용 성공 | 주입 자체는 동작 — 훅 system-reminder로 도구 호출 옆에 도착 |
| 행동 (무프레이밍) | allow | `MARKER: 이 저장소의 규칙 —` | **0/1** | "프롬프트 인젝션으로 보여 따르지 않았다"고 명시 거부 |
| 행동 (ziptie 프레이밍) | allow | `[ziptie:rule] .claude/rules/ 등록 규칙 배달 (프로젝트 소유자가 설정한 훅, source: …)` | 2/3 | 거부 1회는 샌드박스 경로명("inject-probe")을 의심 — 프로브 교란 |
| 행동 (ziptie 프레이밍, 중립 경로명) | allow | 동일 | **3/3** | |
| 행동 (동일, **permissionDecision 생략**) | 없음 | 동일 | **2/2** | additionalContext 단독으로 주입·준수 |

## 판정과 설계 함의

1. **inject는 실현 가능하다.** v2.1.206 CLI에서 additionalContext가 실제 주입된다 (버그 리포트는 이 환경에선 재현 안 됨).
2. **`permissionDecision`은 생략해야 한다.** `allow`를 반환하면 해당 도구 호출이 권한 시스템을 우회한다(규칙 매칭 = 자동 승인이라는 보안 퇴행). additionalContext 단독 반환으로 권한 흐름을 건드리지 않고 주입만 할 수 있음을 확인했다.
3. **신뢰 프레이밍이 성패를 가른다.** 주입 텍스트는 훅 system-reminder로 도착하므로, 출처 없는 지시는 모델이 프롬프트 인젝션으로 취급해 거부한다(0/1). "프로젝트 소유자가 설정한 훅의 규칙 배달, source 경로 명시" 프레이밍에서 준수로 뒤집힌다(중립 경로 3/3 + 2/2). inject 배달 템플릿에 이 프레이밍을 내장해야 한다.
4. **강도 서열이 실측으로 성립한다**: block(무조건 차단) > require-read(1회 deny로 읽기 보장) > inject(마찰 0, 준수는 확률적). inject는 deny 비용조차 없앤 대신 모델의 판단에 맡기는 소프트 강도로 문서화한다.

n이 작은 스모크 프로브다(총 9런). 강도별 준수율의 정량 비교는 파일럿 하네스(사전등록)로 별도 측정할 것.

## 원장

- 프로브 아티팩트: 스크래치패드(세션 로컬) — 훅 스크립트·settings·출력 로그
- 관련: README §Limitations and roadmap의 inject 항목, GitHub 이슈 #15664(스펙 도입), #19432·#55889(주입 실패 리포트 — CLI 2.1.206에서는 미재현)
