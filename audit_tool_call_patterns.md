# md-ledger Tool Call Pattern Audit

**Generated:** 2026-04-02  
**Data source:** claude-tool-stats (76 session files, `~/.claude/projects/`)  
**Scope:** All Claude Code sessions on this machine

---

## 1. Raw Data Shape

| Metric | Value |
|---|---|
| Session files parsed | 76 |
| Total tool calls | 2,202 |
| md-ledger Bash calls | 215 |
| md-ledger success | 184 (85.6%) |
| md-ledger errors | 31 (14.4%) |

### All tool calls in context

| Tool | Calls | Error% |
|---|---|---|
| Bash | 1,044 | 15.3% |
| Read | 646 | 10.8% |
| Edit | 261 | 3.4% |
| Grep | 93 | 0% |
| Glob | 83 | 1.2% |
| Write | 58 | 0% |

---

## 2. First-Order: md-ledger Subcommand Counts

| Subcommand | Calls | Share |
|---|---|---|
| `headers` | 116 | 54% |
| `find-section` | 50 | 23% |
| `index` | 34 | 16% |
| `update` | 14 | 6.5% |
| `find-content` | 12 | 5.6% |
| `query` | 9 | 4.2% |
| `ingest` | 4 | 1.9% |
| `--help` | 4 | — |
| chained (`&&`) | 8 | — |
| piped (`\|`) | 4 | — |

**Signal:** `find-content` is called 4× less than `find-section` (12 vs 50). Both are first-class navigation tools. This asymmetry is behavioral, not a capability gap — errors for `find-content` were only 1 (sibling-call-error, not functional).

---

## 3. First Aggregations: Error Rates by Subcommand

| Subcommand | Errors | Error% | Primary cause |
|---|---|---|---|
| `headers` | 20 | 17.2% | Cross-project invocation (file outside DB dir), sibling-call-errored |
| `update` | 7 | 50% | Exit code 1 (bad row ID or file not found), sibling-call-errored |
| `&&` chains | 5 | 62.5% | Exit code 1 or 2 in chained commands |
| `find-section` | 3 | 6% | Hook guard blocked a prior grep/head in the same chain |
| `find-content` | 1 | 8.3% | Sibling-call-errored (not functional) |

### Error root cause categories

**Cross-project invocations (headers - dominant failure mode)**  
md-ledger was called on files in other project directories with absolute paths (e.g., `md-ledger headers D:/code/skill_last_fm_taste_engine/CLAUDE.md`) where no `ledger.db` exists in that directory. The tool exits 1. Recovery: fallback to `Read(file, offset)`.

**Sibling-call-errored (parallel tool patterns)**  
When md-ledger is issued in parallel with another tool and the sibling fails first, the md-ledger call is cancelled. These are not functional errors — the tool wasn't at fault. Counts: 8 of 41 total errors.

**`--db` flag + wrong row IDs**  
`update --db "path" ROW_ID "text"` used across projects sometimes fails with exit code 1 when row IDs are stale or tables weren't re-ingested. Recovery: raw Read fallback.

**Hook guard interactions**  
3 `find-section` errors came from hook guards blocking a prior `grep` or `head` in the same compound command. The compound command was already prohibited, so md-ledger was never invoked.

---

## 4. Second-Order: Recovery Sequences

### After md-ledger failure → next successful tool

| Subcommand failed | Recovery tool | Count |
|---|---|---|
| `headers` | Read | 9× |
| `headers` | Bash (retry) | 7× |
| `&&` chain | Bash | 4× |
| `find-section` | Bash | 3× |
| `update` | Bash | 2× |
| `update` | Read | 2× |

**Key signal:** `headers` failure → `Read` (9×) means when cross-project `headers` fails, fallback is a raw Read with offset/limit. This is acceptable behavior, but the repeated pattern (mostly on the same cross-project paths like `markkorandacom/profile/_analysis/scoping.md`) suggests a gap: **md-ledger lacks a clean multi-DB or path-overriding invocation pattern**, forcing raw-read fallback.

### Read usage: targeted vs raw

| Read mode | Count | Share |
|---|---|---|
| With offset/limit (targeted) | 398 | 61% |
| Without offset/limit (raw) | 252 | 39% |

Of the 252 raw reads: 82 are `.md` files, 107 are `.py`, 25 are `.txt`.

**Hook effectiveness on raw .md reads:**  
31 of 82 raw `.md` reads were blocked by the PreToolUse hook = **38% block rate**. The remaining 62 slipped through — reasons include files under 50 lines, files in other project contexts where the hook threshold doesn't apply, and files that the hook doesn't check (e.g., `CLAUDE.md`, `MEMORY.md` in system dirs that have separate hook logic).

---

## 5. Higher-Order: Test Suite Gap Analysis

### Test coverage map vs actual usage

| Subcommand | Usage rank | Test file | Coverage quality |
|---|---|---|---|
| `headers` | 1st (116 calls) | test_navigation.py §C | Good — path forms, no-headers case |
| `find-section` | 2nd (50 calls) | test_navigation.py §D | Good — bare/relative/absolute/filter |
| `index` | 3rd (34 calls) | test_navigation.py §A, §G | Good — recursive, dedup, fences |
| `update` | 4th (14 calls) | test_update_cli.py, test_apply_update.py, test_ingest.py | Good — including `--db` flag |
| `find-content` | 5th (12 calls) | test_navigation.py §E | Good — context, filter, subdirs |
| `query` | 6th (9 calls) | test_ingest.py | Partial — covered via ingest integration |
| `ingest` | 7th (4 calls) | test_ingest.py | Basic |

### Identified gaps

**GAP 1 — Cross-project / out-of-DB-dir invocation (no test)**  
The #1 failure mode in production. When `headers`, `find-section`, or `find-content` is called with a path to a file outside the current `ledger.db` directory, it exits 1 with no helpful error. There is no test that asserts a clear, actionable error message in this case.  
_Potential test:_ invoke `headers /absolute/path/outside/db/dir/file.md` from a different `cwd` and assert `returncode != 0` with a message like "No ledger.db found for path — run: md-ledger index /absolute/path/..."

**GAP 2 — Parallel/sibling-call resilience (no test, not really testable)**  
8 errors are artefacts of sibling-call cancellation in Claude's parallel tool dispatch. These can't be unit-tested, but they inflate the error rate and could be suppressed if the tool emitted cleaner exit messages.

**GAP 3 — Windows absolute paths with mixed separators (partial coverage)**  
Production calls frequently use `D:/code/...` (forward-slash Windows absolute paths) in Bash. `test_navigation.py §F.test_uses_forward_slashes_on_all_platforms` covers the storage side, but there is no CLI-level test that passes a `D:/...`-style absolute path to `headers` or `find-section`.

**GAP 4 — `find-content` behavioral underuse (not a gap in tests, but in CLAUDE.md guidance)**  
`find-content` is called 4× less than `find-section` despite being equally important. No functional failures. The imbalance is instructional: the CLAUDE.md and hook guidance emphasize structural navigation over content search. Consider adding a decision rule or example that explicitly prefers `find-content` for searches that aren't already header-anchored.

**GAP 5 — `query` subcommand error paths (partial)**  
`query` is used 9× in production. test_ingest.py covers happy-path query via the Python API but does not test the CLI-level `md-ledger query` invocation, or the case where `--h2` matches no rows. The `--h2` case-mismatch bug was fixed (commit aba9553) but there's no regression test for it in the CLI test layer.

**GAP 6 — Auto-reindex across the full CLI workflow (partial)**  
test_navigation.py §G.test_edit_file_then_find_updated_content covers auto-reindex via `find-content`. There is no integration test for auto-reindex + `find-section` → `Read(offset)` chain, which is the dominant production workflow (headers: 116, find-section: 50).

---

## 6. Recommendations

### Immediate (test gaps)

| Priority | Action |
|---|---|
| High | Add test: `headers` on absolute path outside DB dir emits actionable error (not bare exit 1) |
| High | Add regression test: `query --h2 <section>` CLI-level, including case-insensitive match and no-match case |
| Medium | Add CLI-level test: `find-section` and `find-content` with Windows-style absolute paths (`D:/...`) |
| Low | Add integration test: stale-file auto-reindex is visible in `find-section` output (not just `find-content`) |

### Behavioral (CLAUDE.md / hook tuning)

| Priority | Action |
|---|---|
| Medium | Add `find-content` usage example to CLAUDE.md decision tree with an explicit note: "use when you don't know the exact header name" — the 4× imbalance vs `find-section` suggests it's being under-triggered |
| Low | Consider adding a `--db` flag lookup hint to the `headers` error message for cross-project invocations, to reduce the raw-Read fallback pattern |
| Low | Hook block rate on raw `.md` reads is 38% — audit which `.md` file categories are slipping through if tighter enforcement is desired |

---

## Appendix: Full Bash verb error table (from failure_analysis.py)

| Verb | Fails | OK | Total | Fail% | Config |
|---|---|---|---|---|---|
| md-ledger | 31 | 184 | 215 | 14.4% | review |
| py | 23 | 131 | 154 | 14.9% | review |
| cd | 22 | 70 | 92 | 23.9% | warn |
| git | 11 | 32 | 43 | 25.6% | (unclassified) |
| python3 | 12 | 36 | 48 | 25.0% | (unclassified) |
| cat | 5 | 14 | 19 | 26.3% | deny_md |
| grep | 8 | 44 | 52 | 15.4% | deny_md |
| head | 3 | 14 | 17 | 17.6% | deny_md |
| tail | 1 | 2 | 3 | 33.3% | deny_md |
| ls | 15 | 143 | 158 | 9.5% | review |

_failure_analysis.py exported to `/d/code/claude-tool-stats/failure_analysis.json`_
