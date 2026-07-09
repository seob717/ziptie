---
description: Extract rules from CLAUDE.md and its referenced documents and compile them into trigger-bound rule files
argument-hint: "[document path (omit for CLAUDE.md and all its @references)]"
---

# /ziptie:compile

Compile rules with the following procedure.

## 1. Collect input
- If an argument is given, read only that document; otherwise read the project CLAUDE.md and every `@path` document it references.

## 2. Extract rules
From each document, extract only rules that "are effective when recalled right before a specific action." Criteria:
- Can it be tied to a specific tool call? (creating a PR, committing, editing a specific file, running a specific command)
- General guidance that can't be tied to an action (tone, coding style at large) is **not a compilation target** — skip it and report it at the end as a list of "uncompilable rules."

## 3. Infer triggers
For each rule, set a `tool` (Bash|Edit|Write) and a `pattern` (Python regex). Examples:
- PR rules → tool: Bash, pattern: `gh\s+pr\s+create`
- Commit conventions → tool: Bash, pattern: `git\s+commit`
- Migration file rules → tool: Edit, pattern: `migrations/`
A Bash rule's pattern matches against the command string; an Edit/Write rule's pattern matches against the file path.

## 4. Decide strength
- The default is `require-read` (deliver the rule only once per session and let retries through).
- Only actions a document explicitly marks as "absolutely forbidden" get `block`.

## 5. Generate rule files
For each rule, create `.claude/rules/<kebab-case-name>.md`. If there is an original document, put its project-relative path in `source` and write only a one-line summary in the body (no copy-paste, since the original is read at delivery time):

```markdown
---
name: pr-rules
trigger:
  tool: Bash
  pattern: gh\s+pr\s+create
source: docs/pr-rules.md
strength: require-read
enabled: true
---
PR creation rules — title format, required sections, reviewer assignment.
```

## 6. User review
Show the list of generated rule files as a table (name / trigger / strength / source), and along with the list of uncompilable rules, ask "is there anything to fix?" An overly broad regex becomes a false positive, so scoping it conservatively narrow is the default.
