# CATALOG:
# id: md-ledger-001
# kind: ticket
# status: open
# origin: _index (monorepo-steward), finding 2026-06-16 (registry sweep)
# htttw_contribution: 0 — none. Walked C1–C8: a test-import fix carries no word-arc claim and serves only daily tooling reliability, not even infrastructurally to htttw's terminal. Valid recorded 0 (ADR-0010), not inflated.
# judgment_applied: no-punt (core is firmly ours), cold-open, htttw-score (ADR-0010), bug-verified-on-disk
# provenance: filed-by proxy-steward (dispatched from _index, user-authorized 2026-06-20)
# decided-by: proxy-steward (dispatched from _index, user-authorized 2026-06-20)
# consumes: inbox/finding_from-_index_2026-06-16_broken-test-imports.md
# produces: 3 fixed test imports + passing ingest/update suite + corrected README line
# effort: S
# tags: tests, ci-hygiene, ingest, update, import-path
# gloss: 3 test files fail pytest collection on a stale `from main import` path, leaving table ingest/update untested.

# Fix the stale `from main import` in 3 test files (ingest/update surface is currently uncollected)

**Origin (recovered):** _index (monorepo-steward) filed this via the 2026-06-16 registry sweep as a declinable finding. Their words: pytest runs 83/86 — `test_apply_update.py`, `test_edge_cases.py`, `test_ingest.py` error at collection with `ModuleNotFoundError: No module named 'main'` because they `import from main import ...` rather than `from md_ledger_tool.main import ...`. These three cover table ingestion + update, so that surface "is currently untested." They also noted the README line claiming "pytest runs all tests" is now inaccurate. Bug confirmed on disk 2026-06-20: all three files in `md_ledger_tool/tests/` still carry the bad import.

**The ask (in this project's terms):** Repair the import path in the three test modules so the ingest/update test surface is collected and runs again, then re-truth the README's test claim.

**In-scope core / drift split (ADR-0003):** Firmly ours — the import path, the suite passing, and the README line all live in this repo and are owned here. No drift; nothing routes outward.

**htttw service:** None. md_ledger is the monorepo's .md-navigation tool; a test-collection fix serves daily tooling reliability, not htttw's argument about words/attention/legibility. Score 0 recorded deliberately (ADR-0010: a 0 is a valid outcome), not skipped.

**Move:** In `md_ledger_tool/tests/{test_apply_update.py, test_edge_cases.py, test_ingest.py}` change `from main import ...` to `from md_ledger_tool.main import ...`. Run `pytest`; confirm 86/86. Correct the README line that claims pytest runs all tests if it no longer needs the caveat.

**Done-when:** `pytest` collects and passes all 86 tests (no collection errors); `grep -rn "from main import" md_ledger_tool/tests` returns nothing; README test claim matches on-disk reality.

**Cross-links:** inbox/finding_from-_index_2026-06-16_broken-test-imports.md (source); README.md (test claim); ADR-0004 (findings route to _index, registered + routed onward).
