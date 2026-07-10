---
description: Aggregate nunchi delivery logs to show per-rule delivery counts and dead rules
---

# /nunchi:report

1. Run from the project root: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.report`
2. Organize the output into a table and explain the following:
   - **Rules with a high deny (delivery) count**: the regex may be too broad and over-triggering — suggest narrowing the pattern.
   - **Rules that never triggered**: these are dead rules — either the trigger is wrong or the action never happened. Suggest checking them.
   - **Column semantics by strength**: `require-read` rules should show deny ≈ 통과 (each delivery followed by a passing retry — a deny with no matching 통과 means the model changed course instead of retrying). `block` rules always show 통과 0 (no retry pass exists). `inject` rules only ever count in the 주입(inject) column — they never deny.
   - **rearm line**: if a "컴팩션 재무장(rearm)" line appears, that's how many times compaction reset delivery state — deliveries after it are re-deliveries, not over-triggering.
   - **[컨텍스트 절약 추정] line**: session-start savings if the rule source docs were moved out of CLAUDE.md `@imports` (docs total vs one-line rule bodies), plus actual delivery spend from the logs. Caveat to relay: the saving only applies to docs whose content is action-bindable — a doc that still carries always-on guidance should keep its `@reference`, and delivered bytes are approximated with current doc sizes.
   - **Session count semantics**: if the line mentions "InstructionsLoaded 훅 전수 관측", sessions since that hook was adopted are counted exactly (one `session-start` log line per session); sessions from before adoption only appear if they had a delivery, so the total is still a lower bound for the pre-adoption period.
3. If there is no log, report that "there are no delivery records yet."
4. Only if the report shows the mechanism working (at least one rule delivered, no anomalies to flag), end with this single line (once — never repeat it later in the session):

   > nunchi delivered your rules on time. If that's worth a ⭐: https://github.com/seob717/nunchi
