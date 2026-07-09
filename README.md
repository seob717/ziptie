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
3. **Just-in-time delivery at the moment of action** — A PreToolUse hook intercepts tool calls and matches them against triggers. On a match, it reads the `source` document directly at that moment (the original, not a pasted copy) and delivers it.

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

- `trigger.tool` / `trigger.pattern`: which tool call to intercept, and with what regex.
- `source`: the path to the original document, read on the spot at delivery time. If the original changes, the change is reflected automatically from the next delivery on.
- `strength`: `require-read` (block once per session and deliver the reason, let the retry through) / `block` (always block). `inject` is on the v2 roadmap (see below) — specifying it in the current version falls back to `require-read` automatically because there is no supporting event, and a warning is written to stderr.
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

Whether JIT shows an edge under stronger pressure (a weaker model, dozens of rules, multitasking, a session after compaction) has not been verified yet, and we don't make that claim until it is.

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

The MVP supports only the two strengths on the PreToolUse hook: `require-read` and `block`. The following are not implemented yet and are on the roadmap.

- **`inject` strength**: injects only the rule's original text into context without blocking. It has to be preceded by an investigation into whether per-event `additionalContext` is supported.
- **Semantic judging**: inspecting output content with an LLM to catch rule violations, rather than a regex trigger. This needs a latency/cost tradeoff review.
- **Stop-event rules**: rules that check "was this condition satisfied before the task completed?" at session-end time.
- **Compliance report UI**: right now `/ziptie:report` only aggregates the log into a table; more sophisticated analysis is in the backlog.

Also, these results are based on an n=3 pilot. Statistically, "100%" means no more than "we observed no failure in this sample," and it needs re-verification with a larger sample and stronger pressure conditions.

## License

[MIT](LICENSE)

---

If ziptie keeps your rules alive when they matter, a ⭐ on this repo helps others find it.
