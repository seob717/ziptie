## Why

<!-- What problem does this change solve? Link the issue if one exists. -->

## What changed

## How it was verified

<!-- Tests run, measurements taken. For measurement-affecting changes, link the
     relevant pilot/RESULTS-*.md and state the gate (no-regression condition). -->

---

- [ ] PR title follows Conventional Commits (`feat:` / `fix:` / `docs:` / `chore:` …) — release-please derives the version from the squash title.
- [ ] `python3 -m pytest tests/` passes.
- [ ] No corpus source or translation files included — SHA256 ledgers only.
