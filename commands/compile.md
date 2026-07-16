---
description: Extract rules from CLAUDE.md and its referenced documents and compile them into trigger-bound rule files
argument-hint: "[document path (omit for CLAUDE.md and all its @references)]"
---

# /nunchi:compile

Compile rules with the following procedure.

## 1. Collect input
- Argument: $ARGUMENTS
- If an argument is given, read only that document; otherwise read the project CLAUDE.md and every `@path` document it references.

## 2. Extract rules
From each document, extract only rules that "are effective when recalled right before a specific action." Criteria:
- Can it be tied to a specific tool call? (creating a PR, committing, editing a specific file, running a specific command)
- Content that can't be tied to an action is **not a compilation target** — skip it, but classify what you skip into two lists for the final report (§6):
  - **Procedure** — an ordered, multi-step how-to or workflow (release steps, migration order, environment setup). The right home is a Claude Code *skill*: a skill loads only its description at session start and its body on invocation — the same context economics as a nunchi rule, for content that is a *how* rather than a *before*. Report it as a **skill candidate**, quoting the passage that makes it procedural. Boundary: a checklist to run **before one specific action** ("before pushing, review the diff and run the checks") is a rule bound to that action, not a skill candidate — being multi-step doesn't disqualify it (measured misroute: `pilot/RESULTS-compile-bench-skillroute.md`); skill candidates are only for how-tos with no single triggering tool call.
  - **Always-on guidance** — tone, general coding style, facts that must color every turn: stays in CLAUDE.md. **When unsure, classify here** — never propose moving content out of CLAUDE.md on a guess, and never route anything action-bindable into a skill candidate (an action rule compiles; a skill candidate is only for what step 1 of this section already rejected).
- **Tables, fenced code blocks, and list items are rule candidates on equal footing with prose.** A constraint doesn't stop being a rule because it sits in a table row or next to a code sample. But distinguish usage catalogs from constraints: a commands table that only lists what you *can* run is documentation, not a rule — it becomes a rule only when the document attaches an obligation, prohibition, or ordering to the action (must / never / before / after / only).
- **One rule per trigger**: when one sentence bundles requirements aimed at *different* triggers ("run X after editing A; run Y before pushing"), split them so each rule carries its own trigger and strength. Do NOT split an enumeration that shares one trigger, one strength, and one source ("run `make format`, `make lint`, `make test` before creating a PR" stays a single rule) — same-trigger copies would deliver the same source document multiple times for nothing.

## 3. Infer triggers
For each rule, set a `tool` (Bash|Edit|Write) and a `pattern` (Python regex). Examples:
- PR rules → tool: Bash, pattern: `gh\s+pr\s+create`
- Commit conventions → tool: Bash, pattern: `git(\s+-\S+(\s+\S+)?)*\s+commit`
- Migration file rules → tool: Edit, pattern: `migrations/`
- Content rules ("no console.log") → tool: Edit, pattern: `console\.log`, field: `new_string`, path: `\.(ts|tsx)$`
A Bash rule's pattern matches against the command string; an Edit/Write rule's pattern matches against the file path. Add `field: <tool_input key>` under `trigger` to match against a specific input field instead (e.g. `new_string` for edit content, `content` for Write). Two hard-won cautions:
- **Content rules must carry a `path:` regex** (ANDed with `pattern` against the file path) scoping them to code files — otherwise the rule fires on example code inside markdown, comments, and even its own source document.
- **Git command patterns must allow global options** — `git\s+commit` misses `git -C <dir> commit`; use the `git(\s+-\S+(\s+\S+)?)*\s+<subcommand>` shape.
- **File content/structure rules bind to BOTH Edit and Write**: a rule constraining what a file may contain ("no console.log", "every ViewModel follows this structure", "storyboards are banned") applies when modifying an existing file AND when creating a new one. Emit a pair — one rule with `tool: Edit`, one with `tool: Write` — sharing pattern, path, strength, and source (a content rule's Edit twin matches `field: new_string`, its Write twin `field: content`). This is "one rule per trigger" applied across tools: a different tool is a different trigger, and a single-tool binding silently leaks the other path (measured: `pilot/RESULTS-compile-wild-ko.md`). Rules about the act itself stay single-tool ("never edit committed migrations" → Edit only; "don't create new top-level modules" → Write only).

## 4. Decide strength
- The default is `require-read` (block once per session with the rule as the reason, let the retry through — guarantees a read at the cost of one retry).
- Actions the document explicitly prohibits get `block`. **Judge by the speech act — advice, obligation, or prohibition — not by surface wording, in whatever language the document is written.** An imperative form can still be advice: "avoid barrel files" recommends, it does not ban. Calibration examples:
  - Prohibition (`block`): "Never …", "Do NOT …" (en) · "절대 …하지 마세요", "…금지" (ko) · "絶対に〜しないでください" (ja) · "NUNCA …", "No uses …" (es)
  - Recommendation (stays `require-read` or `inject`): "avoid …", "prefer …" (en) · "…은 피하세요", "…지양" (ko) · "〜は避けてください" (ja) · "Evita …", "prefiere …" (es)
- Use `inject` for advisory rules where even one blocked attempt is overkill (style reminders, soft conventions): the rule is delivered alongside the tool call with zero friction, but compliance is left to the model's judgment rather than forced by a retry.

## 4.5 Confirm low-confidence judgments (interactive only)

Some §2–§4 judgments are measured to be wrong often enough that silently finalizing them is worse than one short question. Before generating files (§5), collect the judgments matching a low-confidence pattern below and ask the user about **at most 3 of them per compile** — pick the ones where a wrong call does the most damage (a wrong `block` halts legitimate work; a wrong trigger never fires; a wrong skill-candidate routing drops an enforceable rule). Each question quotes the source passage, states the tentative judgment, and offers the alternative — answerable in one word. Flagged items beyond the cap are finalized as usual and marked in the §6 review table so review starts with them.

Low-confidence patterns (each observed as a misjudgment in the benchmarks — extend this list only with measured evidence):

- **Strength on the recommendation/prohibition boundary** — after applying §4's speech-act calibration the reading is still arguable (hedged prohibitions, translated nuance, advice and ban mixed in one sentence). Measured: 12–18% of strength assignments differ from gold (`pilot/RESULTS-strength-guidance.md`, `pilot/RESULTS-compile-wild-ko.md`).
- **Trigger inferred beyond the document** — the document names no command or tool for the action, so `tool`/`pattern` come from convention rather than the text (e.g. the doc says "before creating a PR" but never mentions `gh`; a team on different tooling gets a rule that never fires).
- **Procedure/rule boundary** — multi-step content where §2's single-triggering-action test is arguable either way. Measured misroute: 1/24 (`pilot/RESULTS-compile-bench-skillroute.md`).

Never question high-confidence judgments: explicit prohibition wording matching §4's calibration examples, triggers whose command the document itself names, or a checklist clearly bound to one action. No flagged items → skip this step silently.

**Non-interactive runs ask nothing**: in headless or non-interactive execution (`claude -p`, CI), skip the questions entirely and finalize every judgment exactly as before — the flags still appear in the §6 review table.

## 5. Generate rule files
For each rule, create `.claude/rules/<kebab-case-name>.md`. If there is an original document, put its project-relative path in `source` and write only a **one-line summary** in the body. Two reasons, both hard requirements: the original is read at delivery time (so a pasted copy would drift), and Claude Code's native `.claude/rules/` loader injects the body at session start (so a long body would enter context twice — the body is the always-on declaration, the source is the JIT payload):

**Recompiling over existing rules**: a rule file that already matches its source document is kept — but "matches the document" is not enough. Also check every kept rule against the current trigger guidance (content rules must carry `path:`; git patterns must allow global options). If a kept rule violates it, don't keep it silently: include it in the review table with a proposed upgraded trigger, marked as an upgrade.

Filename convention: base the filename on the source document's filename in kebab-case (e.g. `docs/pr-rules.md` → `pr-rules.md`). If a single document yields multiple rules, append a content-based suffix to disambiguate (e.g. `pr-rules-title.md`, `pr-rules-reviewer.md`); a dual-bound pair (§3) disambiguates as `-edit` / `-write` (e.g. `no-console-log-edit.md`, `no-console-log-write.md`). If the resulting filename collides with an existing rule file, confirm with the user before overwriting it.

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

## 5.5 Propose dropping covered `@references`

If every rule extracted from an `@referenced` document was compiled (nothing from it landed in the uncompilable list), tell the user the `@path` line in CLAUDE.md can be removed: the document will then load just-in-time via the rule's `source` instead of at every session start (measured: `pilot/PROBE-context-economics.md`). If the document also produced uncompilable always-on guidance, do NOT propose removing it — say which part still needs the `@reference`. Removing the `@reference` does not orphan the document: the delivery engine notices edits to any compiled rule's `source` document and reminds about recompiling, once per session (issue #17).

## 5.6 Offer a rule-document convention watcher (opt-in)

If the user's rule documents follow a path convention (e.g. `docs/*-rules.md`), offer to generate one extra rule that watches the convention itself, so a newly created rule document prompts a compile instead of silently never being compiled. Ask for the convention — never guess it — and skip this step entirely if the user has none (default: don't generate). The watcher is an ordinary rule file, so it rides the existing load/match/session-marker path:

```markdown
---
name: rule-doc-convention
trigger:
  tool: Write
  pattern: docs/.*rules.*\.md$
strength: inject
enabled: true
---
New rule document — run /nunchi:compile <its path> to compile it into trigger-bound rules.
```

## 6. User review
Show the list of generated rule files as a table (name / trigger / strength / source — with a ⚠ mark on rules that carried a §4.5 low-confidence flag but weren't asked about), and along with the two skip lists from §2 — **skill candidates** (each with its quoted procedural passage) and **always-on guidance** — ask "is there anything to fix?" An overly broad regex becomes a false positive, so scoping it conservatively narrow is the default.

Skill candidates are proposals only — create nothing unless the user approves one. On approval, scaffold `.claude/skills/<kebab-case-name>/SKILL.md` with a one-line `description` (what it does + when to use it) and the quoted procedure as the body, and note that the passage can then be removed from the source document. A document left with only compiled action rules and accepted skill candidates (no always-on guidance) qualifies for the §5.5 `@reference` removal.

If the user requests a change, edit only the affected rule file(s) and show the table again for another round of review. If the user requests no changes, treat the compilation as complete.

## 7. Closing lines
If at least one generated rule has a `source` document, show a one-line before/after right after the review is settled — byte-based, with tokens only as a rough estimate (tokenizers differ):

> always-on 컨텍스트: <sum of source doc bytes> → <sum of one-line rule bodies> (−N%), 상세 문서는 트리거 시에만 전달 — §5.5에서 @참조를 제거한 경우 기준.

Only if at least one rule file was generated, end the final message with this single line (once — never repeat it later in the session):

> Setup complete. If nunchi is useful, a ⭐ helps others find it: https://github.com/seob717/nunchi
