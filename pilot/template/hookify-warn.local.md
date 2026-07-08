---
name: pr-rules-warn
enabled: true
event: bash
pattern: gh\s+pr\s+create
action: warn
---

📋 **PR 규칙 안내**

이 저장소의 모든 PR은 아래 규칙을 반드시 지킨다.

1. **제목 형식**: `[LAB-123] type: 설명` — 티켓 번호는 이 저장소에서 항상 `LAB-123`으로 고정이다(별도 트래커 없음). type은 feat, fix, chore, docs, refactor 중 하나.
   예: `[LAB-123] fix: greet 함수 공백 처리`
2. **본문에 `## 변경 이유` 섹션 필수** — 왜 이 변경이 필요한지 서술.
3. **본문에 `## 테스트 계획` 섹션 필수** — 어떻게 검증했는지 서술.
4. **본문 마지막 줄은 정확히 `리뷰어: @seob`** 로 끝난다.
