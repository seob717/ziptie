---
name: readme-translate
description: Create or re-sync a translated README snapshot (README.<lang>.md) from the canonical English README.md, preserving measured claims and identifiers while writing natural target-language prose. Use when translating the README, fixing translation style, or syncing snapshots at release time.
---

# readme-translate

Translate the canonical `README.md` into `README.<lang>.md` as a **release-time snapshot**. The English README is always canonical; translations never lead.

## Procedure

1. **Pin the base.** Record the current release tag and main commit (`git log -1 --format=%h origin/main`, `gh release view --json tagName`). These go in the snapshot header.
2. **Read `README.md` in full.** Never translate from an older translation — always from the current English canonical.
3. **Write the header block** at the top of the translation:
   - Language switcher linking every existing README language, e.g. `[English](README.md) | **한국어**`. Add the new language to the switcher of *all* other READMEs too.
   - Snapshot note (blockquote): this is a translation of the English README, base release + commit, English wins on any mismatch, synced at release time only.
4. **Translate section by section** following the style rules and glossary below.
5. **Run the gate check** (mandatory, before any commit):
   ```bash
   python3 .claude/skills/readme-translate/scripts/check.py README.md README.ko.md --banned 배달 재무장 강도 캐비앗
   ```
   Fix every hard failure; review every reported soft item line by line.
6. **PR** per `.claude/rules/pr-rules.md` (`docs:` title; body states base commit and gate results).

## Style rules

Write target-language technical prose, not translated English:

- **Break the source syntax.** Split multi-clause English sentences; reorder to the target language's natural word order. If a sentence reads like it was translated, rewrite it.
- **Translate meaning, never idioms word-for-word.** "upfront freight", "credit where due", "scope map, not a scoreboard" → render the *point* in a natural target-language phrasing.
- **No transliterated loanwords when a common native word exists** (ko: "캐비앗" → 한계/단서).
- **Product terms use commonly understood words** — English original in parentheses at first mention, target language only afterwards.
- **Tone**: plain declarative documentation register (ko: 합니다체, consistent throughout).

## Never translate

- Fenced code blocks — byte-identical to canonical, including comments inside them.
- Commands (`/nunchi:compile`, `gh pr create`), frontmatter keys and values (`strength`, `require-read`, `inject`, `source`), log values (`rearm`, `deny`), tool names, file paths, URLs.
- The tagline (*"Rules with nunchi — delivered before you have to ask."*) stays in English.
- Measured numbers, table values, and their qualifiers — identical to canonical, including every caveat and limitation paragraph (ceiling effect, unmet gates, withheld superiority claims). Dropping a humility clause is a gate failure, not a style choice.

## Glossary — Korean (ko)

Decided in #29 (owner decision — do not relitigate):

| English | Use | Banned |
|---|---|---|
| delivery / deliver | 전달 | 배달 |
| re-arm | 재활성화 | 재무장 |
| strength (concept in prose) | 강제 수준 (key stays `strength`) | 강도 |
| inject / injection | 주입 | — |
| caveat | 한계 / 단서 | 캐비앗 |
| compaction | 컴팩션 | — |
| trigger | 트리거 | — |
| rule (the norm) / rule file | 규칙 / 룰 파일 | — |
| dead rule | 죽은 룰 | — |
| just-in-time (JIT) | JIT (첫 언급에 병기) | — |

When adding a new language, add a `## Glossary — <lang>` section here first (terms + banned list), then pass that banned list to the gate check.

## Gate check (what `scripts/check.py` enforces)

- **Hard fail** — numbers present in canonical but missing in the translation (multiset over `\d+(?:[.,]\d+)*%?`); fenced code blocks not byte-identical; any banned term present.
- **Soft report (review by hand)** — numbers only in the translation (must be explainable as the snapshot header or spelled-out English numbers rendered as digits, e.g. "a third" → "3분의 1"); inline-code spans that differ from canonical.
