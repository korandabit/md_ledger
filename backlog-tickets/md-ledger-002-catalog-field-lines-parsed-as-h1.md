# CATALOG:
# id: md-ledger-002
# kind: ticket
# status: open
# origin: _index :: backlog-standardization fanout 2026-06-20 (surfaced by multiple proxy subagents)
# htttw_contribution: 0 — none. Walked C1–C8: a header-parser/schema fix carries no word-arc claim; tooling reliability only, no infrastructural thread to htttw's terminal. Valid recorded 0 (ADR-0010).
# judgment_applied: no-punt, cold-open, htttw-score, route-to-owner (md_ledger owns the parser)
# provenance: filed-by proxy-steward (dispatched from _index, user-authorized 2026-06-20)
# consumes: the `# CATALOG:` ticket schema (ADR-0011); md_ledger's header parser
# produces: a parser fix or schema decision so CATALOG field-lines stop inflating the header index
# effort: S
# tags: md-ledger, parser, catalog-schema, header-index, cross-cutting
# gloss: md-ledger parses `# field:` lines inside a CATALOG block as H1 headers, polluting every standardized project's header index

# md-ledger reads `# CATALOG:` field-lines as H1 headers

**Origin (recovered):** The 2026-06-20 monorepo backlog-standardization fanout (ADR-0011) gave 16 projects a `backlog-tickets/` dir, one `# CATALOG:`-blocked `.md` per ticket. The CATALOG block writes each field as a `#`-prefixed line (`# id:`, `# kind:`, `# status:`, … ~12 lines). md-ledger treats any line starting with `#` as a header, so every ticket file registers ~12 spurious H1 entries in the header index. Multiple proxy subagents (claude-tool-stats, nlp-for-llm-corpus, others) flagged it independently.

**In-scope core (md_ledger's):** the header parser is md_ledger's. The cleanest fix lives here: when a file (or region) is a `# CATALOG:` block, skip the `# field:` lines (e.g. don't treat `#` lines as headers until after the blank line that ends the block, or recognize the `# CATALOG:` sentinel and skip its field-lines).

**Drift (named, routes elsewhere):** the alternative fix — change the CATALOG schema to use a non-`#` field prefix — is **not** md_ledger's call; it belongs to `_index` / the `intake-translator` skill (schema owner). Do not change the schema from here; if md_ledger judges the parser fix wrong, route that back to `_index` as a consumer-ask.

**htttw service:** none (0). Tooling.
**Move:** decide parser-side skip vs. escalate schema question; implement the skip if chosen; add a test over a sample CATALOG file asserting only the real `#`-title registers.
**Done-when:** a CATALOG ticket file indexes its real title as the only header (or the schema question is routed to `_index` with reason).
**Cross-links:** ADR-0011 (backlog-as-inbox), intake-translator skill (schema owner), the 2026-06-20 fanout record in `_index/outputs/backlog-standardization-dispatch_procedure.md`.

decided-by: proxy-steward (dispatched from _index, user-authorized 2026-06-20)
