---
description: Aggregate ziptie delivery logs to show per-rule delivery counts and dead rules
---

# /ziptie:report

1. Run from the project root: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.report`
2. Organize the output into a table and explain the following:
   - **Rules with a high deny (delivery) count**: the regex may be too broad and over-triggering — suggest narrowing the pattern.
   - **Rules that never triggered**: these are dead rules — either the trigger is wrong or the action never happened. Suggest checking them.
3. If there is no log, report that "there are no delivery records yet."
