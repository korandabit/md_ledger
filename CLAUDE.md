# MD Ledger Tool - Claude Code Integration Guide

**Default tool for all Markdown operations in Claude Code sessions.**

This tool provides token-efficient, structure-aware access to Markdown files through persistent indexing and automatic freshness management.

---

## Session Start

- Read `backlog-tickets/` for this project's open work queue — one `# CATALOG:`-blocked file per ticket (ADR-0011). Cross-project work-asks arrive here as native tickets (filed by the sender at send time).
- The durable cross-project record is the monorepo dialog-log (`D:/Dropbox/_index/dialog-log/`), not local mail. The `inbox/` channel is retired (ADR-0013).

---

## Core Principle

**Always use md-ledger for Markdown files.** It provides:
- Structural awareness (header hierarchy)
- Content search with section context
- Automatic index freshness (lazy reindex)
- Persistent cross-session knowledge
- Significant token savings (targeted reads vs full file loads)

---

## Workflow: Markdown File Operations

### 1. On Project Start

**Index all markdown files once:**
```bash
md-ledger index . --recursive
```

This creates persistent header index for all `.md` files in project.
- Runs once per project (or when new files added)
- Takes ~175ms for 47 files
- Index auto-updates on file modifications

### 2. Navigation: Find Sections by Header

**Use case:** Need to read/update a specific section

```bash
md-ledger find-section "Installation"
# Output: README.md:23-45 (H2 "Installation")

# Then targeted read:
Read(README.md, offset=23, limit=22)
```

**Token cost:** ~150 tokens (vs 5,000 for full file read)

### 3. Content Search: Find Text with Section Context

**Use case:** Search for content, get section provenance

```bash
md-ledger find-content "pipeline architecture" --context 2
# Output:
#   architecture.md:85
#   Section: System Design > Pipeline Execution
#   Range: lines 80-95
#   Context: [2 lines before/after]

# Then targeted read:
Read(architecture.md, offset=80, limit=15)
```

**Token cost:** ~200 tokens (vs 97,000 for blind search)

### 4. View Document Structure

**Use case:** Understand file organization before reading

```bash
md-ledger headers README.md
# Shows: Full H1-H6 tree with line ranges
```

**Token cost:** ~400 tokens (vs 5,000 for full read)

### 5. Table Data Operations

**For structured table files** (pipe-delimited with row IDs):

```bash
# Ingest tables
md-ledger ingest constraints.md --full

# Query specific rows
python -c "
from md_ledger_tool.main import init_db, query
db = init_db()
rows = query(db, h2='constraints', type_filter='definition')
for row in rows:
    print(row[0], row[2])  # row_id, text
"

# Update row
md-ledger update C171 "Updated content here"
```

---

## Complete Command Reference

### Indexing
```bash
md-ledger index .              # Index current directory
md-ledger index . --recursive  # Scan subdirectories
md-ledger index file.md        # Index single file
```
- Auto-reindexes on file modification (mtime-based)
- No manual reindex needed

### Navigation
```bash
md-ledger headers file.md                    # Show header tree
md-ledger find-section "query"               # Search headers
md-ledger find-section "query" --file f.md   # Limit to file
```

### Content Search
```bash
md-ledger find-content "text"                # Search content
md-ledger find-content "text" --context 5    # With context lines
md-ledger find-content "text" --file f.md    # Limit to file
```

### Table Operations
```bash
md-ledger ingest file.md --full              # Ingest all tables
md-ledger ingest file.md --h2 section        # Ingest one section
md-ledger update ROW_ID "new text"           # Update row
```

---

## Decision Tree: When to Use What

```
Working with .md file?
├─ Yes, file < 50 lines
│  └─ Use Read tool normally
│
├─ Yes, file 50+ lines
│  ├─ Need to find section by header?
│  │  └─ md-ledger find-section → Read(offset, limit)
│  │
│  ├─ Need to search content?
│  │  └─ md-ledger find-content → Read(offset, limit)
│  │
│  ├─ Need document overview?
│  │  └─ md-ledger headers
│  │
│  ├─ File has structured tables?
│  │  └─ md-ledger ingest → query → update
│  │
│  └─ First time working with file?
│     └─ md-ledger headers (get structure)
│        → md-ledger find-section or find-content
│        → Read(offset, limit)
│
└─ No, not .md file
   └─ Use standard Read/Grep/Edit tools
```

---

## Token Efficiency Examples

### Example 1: Update Changelog
**Blind approach:** Read entire 5,000 token file
**md-ledger approach:**
```bash
md-ledger find-section "unreleased"  # 50 tokens
Read(CHANGELOG.md, offset=5, limit=10)  # 120 tokens
# Total: ~170 tokens vs ~5,000 for full read
```

### Example 2: Find All Pipeline Analysis
**Blind approach:** Read all 47 files = 97,000 tokens
**md-ledger approach:**
```bash
md-ledger find-content "pipeline" --context 0  # 500 tokens
Read(pipelines.md, offset=10, limit=15)  # 180 tokens
Read(architecture.md, offset=80, limit=15)  # 180 tokens
# Total: ~860 tokens vs ~97,000 for blind search
```

### Example 3: Multi-File Context
**Smart Claude approach:** Grep + 3 targeted reads = 3,700 tokens
**md-ledger approach:**
```bash
md-ledger find-section "pipeline"  # 150 tokens
md-ledger headers pipelines.md  # 200 tokens
Read(pipelines.md, offset=10, limit=15)  # 180 tokens
Read(cli_pipeline.md, offset=15, limit=25)  # 300 tokens
# Total: ~830 tokens vs ~3,700 for grep + full reads
```

---

## Python API

### Query Headers
```python
from md_ledger_tool.main import init_db, query_headers

db = init_db()
headers = query_headers(db, "README.md")
# Auto-reindexes if file modified
for h in headers:
    id, file, text, level, start, end, parent = h
    print(f"H{level} '{text}' lines {start}-{end}")
```

### Find Section
```python
from md_ledger_tool.main import init_db, find_section

db = init_db()
results = find_section(db, "Installation")
for file, header, level, start, end in results:
    print(f"{file}:{start}-{end} (H{level} '{header}')")
```

### Find Content
```python
from md_ledger_tool.main import init_db, find_content

db = init_db()
results = find_content(db, "pipeline", context_lines=2)
for file, line, text, section in results:
    if section:
        header, level, start, end, path = section
        print(f"{file}:{line} in '{path}' (lines {start}-{end})")
        print(text)
```

### Table Queries
```python
from md_ledger_tool.main import init_db, query

db = init_db()
rows = query(db, h2='constraints', type_filter='definition')
# Schema: (row_id, h2, text, src, type, file, line_no, status, ingest_ts)
for row in rows:
    print(f"{row[0]}: {row[2]}")  # row_id: text
```

---

## Auto-Reindexing Behavior

**Index freshness is automatic:**
- Tracks file modification time (mtime)
- Lazy reindex on query if file changed
- Silent operation (< 150ms overhead)
- No manual intervention needed

**Example:**
```bash
# Initial query
md-ledger headers README.md
# → Returns cached results (fast)

# Edit README.md externally
vim README.md

# Next query auto-reindexes
md-ledger headers README.md
# → "File modified, reindexing README.md..."
# → Returns fresh results
```

**Performance:** Reindex adds ~120-150ms latency (imperceptible)

---

## Integration with Read Tool

**Always use offset/limit for token efficiency:**

```bash
# Bad (wastes tokens):
Read(large-file.md)

# Good (md-ledger workflow):
md-ledger find-section "Installation"
# → file.md:23-45
Read(file.md, offset=23, limit=22)
```

**Template:**
```python
# 1. Find section
md-ledger find-section "target" --file myfile.md
# Output: myfile.md:X-Y (H2 "Target Section")

# 2. Targeted read
Read(file_path="myfile.md", offset=X, limit=Y-X)

# Result: Only read necessary section, full provenance
```

---

## Common Patterns

### Pattern 1: Explore New Project
```bash
# Index entire project
md-ledger index . --recursive

# Browse main docs
md-ledger headers README.md
md-ledger headers ARCHITECTURE.md

# Search for key concepts
md-ledger find-content "authentication" --context 0
md-ledger find-content "database schema" --context 0

# Targeted deep-dive
md-ledger find-section "Database Design"
Read(architecture.md, offset=X, limit=Y)
```

### Pattern 2: Update Documentation
```bash
# Find target section
md-ledger find-section "API Reference"
# → api.md:150-200

# Read for context
Read(api.md, offset=145, limit=60)  # Slightly wider range

# Edit
Edit(api.md, old_string="...", new_string="...")
```

### Pattern 3: Cross-Reference Analysis
```bash
# Find all mentions with section context
md-ledger find-content "authorization" --context 1

# Output shows each mention's section hierarchy
# Then targeted reads of relevant sections
```

---

## Limitations & Fallbacks

**Known limitations:**
- **`update` only works for ingested table rows**: `update ROW_ID` requires prior `ingest`, and `ingest` only processes markdown tables (header row + `| --- |` separator). Pipe-delimited data lines that aren't proper markdown tables are never ingested → no ROW_IDs → `update` can't reach them. Fix: either (a) extend `ingest` to handle pipe-delimited non-table sections, or (b) ensure pipe-delimited data uses proper markdown table format.
- **`.txt` files now supported** via `--extensions txt` flag: `md-ledger index DIR --extensions txt`. Files with `#`-headers get real header rows. Flat-prose files (no headers) get a sentinel row (level=0) so they appear in `find-content` even with zero headers. Sentinel rows are filtered from `headers`, `find-section`, and `get_section_for_line` output. **Remaining gap:** `--flat-headers` mode for paragraph-level indexing of flat-prose files — not yet implemented.
- **Prune for phantom rows — `gc` / `index --prune-missing` (implemented 2026-06-14).** `index` is add/update-only, so deleted or wrong-path files leave phantom rows that still surface in `find-section` / `find-content`. Drop them with `md-ledger gc` (use `--dry-run` to preview) or fold it into a reindex with `md-ledger index . --recursive --prune-missing`. A row is a phantom when `<db_dir>/<file>` does not resolve on disk; pruning keys on the file path, never on the internal `header_index.id` (which is not exposed by any command). The two mechanisms originally observed across the `D:/code` rotation (final audit 2026-05-27, all 11 projects):
  1. **Vanished-file ghosts** — e.g. `.claude/worktrees/agent-<id>/...` paths from old Claude Code worktree sessions. Caught: deep_drafter 30 rows; essay_linter 499 rows across 64 ghost files; md_ledger itself 110 rows (older PHASE/AUDIT design docs).
  2. **Wrong-path indexing** — file exists but was indexed from a subdirectory (e.g. running `md-ledger index` from inside `_posts/`), so the relative path stored in the ledger doesn't resolve from the directory where `ledger.db` lives. Caught: markkorandacom 880 rows (posts indexed at flat basenames + sibling-subdir entries); music_taste_engine 108 rows (`archive/<file>` files indexed at flat basenames); nlp-for-llm-corpus 2668 rows (mixed mechanisms). Every `find-section` hit on these files returns an unresolvable path.
  **Rotation-wide total: 4295 phantom rows across 6 affected projects (70% concentrated in nlp-for-llm-corpus alone — corpus-heavy projects accumulate phantoms fastest).** Feature (a) — `gc` / `index --prune-missing` — now ships; run it per-project to clear residual phantoms. **Still open:** feature (b), an index-time warning when the `--db` parent dir differs from the index target's parent dir (signals indexing-from-wrong-cwd); and `--flat-headers` paragraph-level indexing (above).

**md-ledger doesn't help when:**
1. File < 50 lines → Just use Read
2. Need full narrative flow → Read entire file
3. Regex pattern matching → Use Grep
4. File not indexed → Run `md-ledger index` first
5. Content is in `.txt` files → Use Grep for content, Read for structure; watch for markdown-style headers that md-ledger can't see

**Fallback to Grep:**
```bash
# md-ledger searches headers + content location
# Grep searches content with regex
Grep(pattern="regex.*pattern", output_mode="content", -C=3)
```

---

## Best Practices

1. **Index early:** Run `md-ledger index . --recursive` on project start
2. **Check structure first:** Use `headers` before deep reading
3. **Use find-content for discovery:** Search then targeted read
4. **Trust auto-reindex:** Don't manually reindex
5. **Combine with Read:** Always use offset/limit for efficiency
6. **Leverage provenance:** Use section hierarchy for context

---

## Error Handling

**File not indexed:**
```
[ERROR] No ledger.db in current directory. Run ingest first.
```
**Solution:** `md-ledger index .`

**No matches found:**
```
No sections found matching 'query'
```
**Solution:** Try broader search or check file is indexed

**Stale index (auto-fixed):**
```
File modified, reindexing README.md...
```
**No action needed:** Auto-reindex handles it

---

## Summary

**md-ledger is the default for all Markdown operations.**

- **Navigation:** find-section + headers
- **Search:** find-content with section context
- **Tables:** ingest + query + update
- **Always:** Combine with Read(offset, limit) for efficiency

**Token overhead: targeted reads only**
**Time overhead: < 150ms (imperceptible)**
**Maintenance: Zero (auto-reindex)**

Use this tool by default. Fall back to Read/Grep only when md-ledger doesn't apply.

---

## Historical moves

| Date | What | Where to / why |
|------|------|----------------|
| 2026-06-21 | `inbox/` retired per ADR-0013 | → backlog + dialog-log; manifest in `_index/history/move-manifest_inbox-retire_md_ledger_2026-06-21.md` |
