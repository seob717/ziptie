# 매칭 판정 프롬프트 — 야생 코퍼스판 (Codex, 셀당 새 세션)

DESIGN-compile-wild-ko §4. PROMPT-match.md와 동일하되 gold 언어 문구 1곳만 변경
(야생 코퍼스는 gold도 문서 언어로 작성됨). 격리 디렉터리에는 문서,
gold.json(커밋 동결본), output.json(해당 셀 컴파일 출력)만 둔다.

---

Read MATCH-CRITERIA (below), gold.json, output.json, and the document in this
directory.

Task: judge every gold rule against the compiler's extracted rules following
the criteria exactly, and write `matches.json` to this directory. Be strict:
when a match is doubtful, prefer miss — this measurement must not flatter the
compiler. Note: gold.json, the document, and the extracted rules' evidence may
all be in the document's own language (e.g. Korean) — judge semantic
equivalence in that language.

## Match rules (strict)

A gold rule MATCHES an extracted rule when ALL of:

1. **Same `tool`** (Bash / Edit / Write).
2. **Same target**: the extracted rule's trigger (pattern/field/path + evidence)
   aims at the same action or content as the gold rule's trigger_intent.
   Semantic equivalence is enough — the wording and language need not be
   identical. `strength` does NOT need to match.
3. **1:1 only**: each extracted rule may be used in at most ONE match across the
   whole file. If one extracted rule covers several gold rules, match it to the
   single closest gold rule; the remaining gold rules are misses. No partial credit.
4. **Partial coverage still matches**: an extracted rule that targets the same
   action as a gold rule but covers only part of the gold rule's compound content
   is still a MATCH — record the omitted clause in the rationale. Do NOT require
   the extracted rule to reproduce every clause of a compound gold rule.

## Verdicts

Every gold rule gets exactly one verdict — either in `matches` or in `misses`.

Miss `category`: `implicit` | `structure` | `reference-depth` | `other`
(same definitions as prior runs; for compiler-self-reported skips use `other`
and quote the uncompilable entry in the note).

Every extracted rule NOT used in `matches` goes to `unmatched_extracted` with a `class`:
- `gold-miss` — a real, action-bindable rule from the document that gold
  failed to list
- `over-extraction` — corresponds to NO real action-bindable rule in the
  document. ONLY for fabrications or non-rules; a narrower-than-gold
  extraction is a match (rule 4), never over-extraction
- `duplicate` — covers the same gold rule as another extracted rule already
  matched

The gold ruleset is FROZEN: record `gold-miss` but propose no additions.

## Output: `matches.json`

```json
{
  "doc": "<doc id>", "lang": "<en|ko|ja|es>",
  "judge": "llm:codex-<version>(<model>)",
  "matches":   [{"gold_id": "g1", "output_rule": "<name>", "rationale": "..."}],
  "misses":    [{"gold_id": "g2", "category": "...", "note": "..."}],
  "unmatched_extracted": [{"output_rule": "...", "class": "...", "note": "..."}],
  "gold_amendments": []
}
```

Integrity (a grader will reject violations): every gold id exactly once in
matches ∪ misses; no output_rule twice in matches; every output_rule is an
exact name from output.json; gold_amendments stays empty.

Do not use the network. Do not read anything outside this directory. Produce
only matches.json.
