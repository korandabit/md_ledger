# CATALOG:
# id: md-ledger-003
# kind: ticket
# status: open
# origin: _index session-close audit 2026-06-21 — uncommitted changes found in this repo from a prior session that ended dirty
# htttw_contribution: 0 — git hygiene.
# judgment_applied: route-to-owner-box, no-blind-commit
# provenance: filed-by monorepo-steward, 2026-06-21
# produces: clean working tree (committed or reverted)
# effort: S
# tags: git-hygiene, orphaned-wip, uncommitted
# gloss: a prior session left this repo dirty — verify the diff and commit if coherent or revert if abandoned.

# Resolve orphaned uncommitted WIP

A prior session ended with this repo dirty. Files (git status 2026-06-21):
- `md_ledger_tool/main.py`, `tests/test_navigation.py` — code + test; verify tests pass, then commit or revert.
- `.gitignore` — the inbox-retirement edit (ADR-0013 tag-along); stage with the above.

**Move:** `git diff` → commit the coherent unit (run tests first) or revert. **Done-when:** working tree clean.
**Cross-links:** _index index-0010 (commit-before-close), ADR-0013.
