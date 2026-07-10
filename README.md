# ziptie

[![License](https://img.shields.io/github/license/seob717/ziptie)](LICENSE)
[![Release](https://img.shields.io/github/v/release/seob717/ziptie)](https://github.com/seob717/ziptie/releases)

*"Zip-tie your rules to the moment they matter."*

A Claude Code plugin that compiles CLAUDE.md rules into trigger-bound hooks and delivers each rule right before the action it applies to.

## The problem

A rule you write in CLAUDE.md is loaded once, at t=0 when the session starts, and that's it. But the moment that rule actually matters is usually dozens of turns later. As context piles up, the model's attention on a rule from the top of the session fades, and once a compaction (summary) passes through, an explicit rule gets demoted to blurry background. A referenced document like `@docs/pr-rules.md` ends up furthest from context at exactly the point where the rule is needed (e.g. when running `gh pr create`). ziptie compiles a rule not as a "declaration at the top of the session" but as an "event listener bound to an action," collapsing the distance between when a rule is needed and when it is delivered to zero.

## How it works

1. **`/ziptie:compile`** — Reads CLAUDE.md and the `@referenced` documents inside it, extracts rules, infers a trigger (tool, regex pattern) for each rule, and compiles them into `.claude/rules/*.md`.
2. **Review the rule files** — The compiled output is plain-text files you can read and edit. Check that the trigger, strength, and source document path are correct, and fix them by hand if needed. These files are the source of truth.
3. **Just-in-time delivery at the moment of action** — A PreToolUse hook intercepts tool calls and matches them against triggers. On a match, it reads the `source` document directly at that moment (the original, not a pasted copy) and delivers it. When several rules match the same tool call, their contents are delivered together in a single block, so one action costs at most one retry.
4. **Re-arm after compaction** — A SessionStart hook scoped to compaction resets the session's delivery markers, so a rule that was already delivered before a compaction (and whose text was therefore summarized away) is delivered again, just-in-time, the next time its trigger matches. No context is spent at compaction time.

## Rule file format

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
Reflect docs/pr-rules.md before creating a PR.
```

- `name`: lowercase letters, digits, and hyphens only (`[a-z0-9][a-z0-9-]*`). A file with an invalid name is rejected with a stderr warning instead of silently misbehaving.
- `trigger.tool` / `trigger.pattern`: which tool call to intercept, and with what regex.
- `source`: the path to the original document, read on the spot at delivery time. If the original changes, the change is reflected automatically from the next delivery on.
- `strength`: three levels, in decreasing order of enforcement.
  - `block` — always block, delivering the rule as the reason. For actions a document marks as absolutely forbidden.
  - `require-read` (default) — block once per session with the rule text as the reason, then let the retry through. One retry buys a guaranteed read.
  - `inject` — deliver the rule via `additionalContext` alongside the tool call, with **zero blocking and zero retry cost**. The delivery carries a provenance framing (project-owner hook, registered rule path, `source` path) because we measured that unframed injected instructions get treated as prompt injection and refused, while framed ones are followed (see `pilot/PROBE-inject.md`). Softer than `require-read`: compliance rides on the model's judgment instead of a forced retry. ziptie never returns `permissionDecision: allow`, so your permission prompts are untouched.
- Body: a summary to deliver instead of, or in addition to, the original document.

## Measured results

Measurement harness: a sandbox repo + a mock `gh` (captures PRs) + 4 machine-gradable PR rules + headless `claude -p` (sonnet), 3 runs per condition. (The full harness is preserved in the `pilot/` directory so it can be re-run.)

| Condition | Description | All-pass | Notes |
|---|---|---|---|
| A | CLAUDE.md only (short context) | 3/3 | Ceiling effect — the rule was just loaded, so it doesn't collapse under this pressure |
| AL | CLAUDE.md only + long context (~60k tokens) | 3/3 | The ceiling effect persists even in long context |
| HW | hookify warn | 3/3 | The warning message never reaches the model, so effectively the same condition as A |
| HB | hookify block | 0/3 | It doesn't populate `permissionDecisionReason`, so the model is blocked without knowing why, destroying 3/3 of the tasks |
| Z | ziptie JIT delivery (real engine, E2E) | 3/3 | Hook fired 3/3 — the first attempt is blocked while the reason (the rule's original text) is delivered, and all retries pass |

What this table shows is *not* an edge of "JIT has a higher compliance rate than CLAUDE.md" — at this pilot's pressure level (4 simple rules, a single task, sonnet), even CLAUDE.md alone (A, AL) held up with a ceiling effect, and we don't hide that result. What the measurement actually supports is three things:

1. **hookify block is harmful.** A block that doesn't communicate the reason destroys 3/3 of the tasks. The same block, when it delivers the reason alongside it (the ziptie way), flips 0/3 → 3/3.
2. **The JIT delivery mechanism itself works and does not hurt the task.** In the E2E with the real ziptie engine attached (condition Z), the hook fired 3/3 normally, and all 3 runs — blocked, then given the reason and retried — completed the task.
3. **Source-document sync and delivery logging actually work.** Because `source` is read every time at delivery, the rule and its original never drift apart, and every trigger, delivery, and block is recorded as JSONL and aggregated by `/ziptie:report`.

**Pressure re-verification (pre-registered):** we then scaled the pressure to 24 rules behind a 3-level `@reference` structure plus the same ~268KB long-context task and re-ran the CLAUDE.md-only condition (design and results: `pilot/DESIGN-pressure.md`, `pilot/RESULTS-pressure.md`). The ceiling held — all-pass stayed 100% across 5 valid runs (40/40 graded checkpoints), so the pre-registered gate for a confirmatory JIT-vs-CLAUDE.md comparison was not met and we did not run it.

**Compaction pressure (pre-registered):** we then forced a `/compact` mid-task and graded only post-compaction behavior (design and results: `pilot/DESIGN-compaction.md`, `pilot/RESULTS-compaction.md`). The CLAUDE.md-only condition produced its first observed rule violation across all experiments (a PR labeled with a value outside the allow-list that lives only in an `@referenced` doc — exactly the detail compaction discards), but at 2/3 all-pass the pre-registered gate was again not met, so no confirmatory comparison was run and no superiority claim is made. What the runs do support: the re-arm mechanism worked in 3/3 treated runs (deliver → compact → re-arm → re-deliver), and JIT delivery still didn't hurt task completion after compaction (3/3 all-pass). Whether JIT shows a compliance edge under stronger pressure remains unverified, and we don't make that claim until it is.

## Requirements

- [Claude Code](https://code.claude.com) with plugin support
- Python 3 — the hook engine and `/ziptie:report` run on the standard library only; no external packages

## Installation

### From the marketplace (recommended)

```
/plugin marketplace add seob717/ziptie
/plugin install ziptie@ziptie-marketplace
```

### From a local directory

```bash
git clone https://github.com/seob717/ziptie.git
claude --plugin-dir /path/to/ziptie
```

Once the plugin loads, the `/ziptie:compile` and `/ziptie:report` slash commands and the PreToolUse hook are active.

## Development

```bash
uvx pytest tests/              # run the test suite (stdlib-only code, pytest as the runner)
uvx pre-commit run --all-files # lint & format (ruff)
```

## Contributing

Issues and PRs are welcome. Commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, …) — [release-please](https://github.com/googleapis/release-please) derives versions and the changelog from them.

## Limitations and roadmap

The following are not implemented yet and are on the roadmap.

- **Content-field triggers**: matching on what is being written (e.g. `new_string` of an Edit) rather than just the command string or file path, so rules like "no console.log in commits" become expressible.
- **Semantic judging**: inspecting output content with an LLM to catch rule violations, rather than a regex trigger. This needs a latency/cost tradeoff review.
- **Stop-event rules**: rules that check "was this condition satisfied before the task completed?" at session-end time.
- **Compliance report UI**: right now `/ziptie:report` only aggregates the log into a table; more sophisticated analysis is in the backlog.

Also, these results come from an n=3-per-condition pilot plus a pre-registered pressure preflight (6 runs). Statistically, "100%" means no more than "we observed no failure in this sample," and any claim of a JIT compliance edge still awaits a pressure level that actually breaks the baseline.

## License

[MIT](LICENSE)

---

If ziptie keeps your rules alive when they matter, a ⭐ on this repo helps others find it.
