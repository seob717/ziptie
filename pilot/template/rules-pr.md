---
name: pr-rules
trigger:
  tool: Bash
  pattern: gh\s+pr\s+create
source: docs/pr-rules.md
strength: require-read
enabled: true
---
PR 생성 규칙 — 제목 형식, 필수 섹션, 리뷰어 지정.
