# MD Ledger Tool - LLM Affordances Guide

This document outlines the core affordances of `md_ledger_tool`, expected behavior, and the minimal knowledge an LLM needs to interact with the tool. It assumes the tool is already installed and `ledger.db` is initialized.

---

## Tool Affordances

### Phase 1: Table Parsing
1. **Targeted ingestion:** Ingest only a specific H2 section from a Markdown file.
2. **Full ingestion:** Ingest all tables from a Markdown file.
3. **Querying:** Retrieve rows by H2 and type (`definition`, `hypothesis`, etc.).
4. **Provenance tracking:** Each row records file, line number, H2, type, status, and ingestion timestamp.
5. **Validation:** Detect malformed rows and skip them with error reporting.
6. **Persistent storage:** All ingested data is stored in `ledger.db` for repeated access.

### Phase 2: Header Navigation
1. **Project-wide indexing:** Scan all .md files and build header tree (H1-H6).
2. **Section queries:** Find sections by header text across all indexed files.
3. **Line boundaries:** Get exact line ranges for targeted reads.
4. **Hierarchy tracking:** Maintains parent-child relationships between headers.
5. **Persistent index:** Header structure stored in DB for instant access.

---

## CLI Usage

### Table Ingestion

**Ingest a full Markdown file:**
```bash
md-ledger ingest example.md --full
# or implicit: md-ledger example.md
```

**Ingest a specific H2 section:**
```bash
md-ledger ingest example.md --h2 constraints
```

### Header Navigation

**Index markdown files:**
```bash
md-ledger index .                    # Current directory
md-ledger index . --recursive        # Scan subdirectories
md-ledger index README.md            # Single file
```

**Query header tree:**
```bash
md-ledger headers README.md
# Shows: H1/H2/H3 structure with line ranges
```

**Find sections:**
```bash
md-ledger find-section "Installation"
# Output: README.md:23-45 (H2 "Installation")
```

**Querying from Python:**
```python
from md_ledger_tool.main import init_db, query

db = init_db()
rows = query(db, h2='constraints', type_filter='definition')
for row in rows:
    print(row)
```

- `h2` specifies the section.
- `type_filter` specifies the row type to filter (optional).
- Returns a list of tuples: `(row_id, h2, text, src, type, file, line_no, status, ingest_ts)`

**Updating rows in the source Markdown:**

Via CLI:
```bash
md-ledger update C171 "Updated content here"
md-ledger update C171 "New text" --db custom.db
```

Via Python:
```python
from md_ledger_tool.apply_update import apply_update

apply_update(row_id='C171', new_text='Updated content here')
```

- Updates both source Markdown file AND database row
- Only updates the `text` column (2nd column)
- Sets `status='updated'` and updates `ingest_ts` to current timestamp
- Fails fast if row_id, file, or line number is invalid
- CLI returns exit code 1 on error for shell scripting

**Note on duplicates/versioning:**
- `INSERT OR REPLACE` during ingestion means last write wins for duplicate `row_id`
- `ingest_ts` enables basic version tracking (most recent timestamp = current version)
- Full version history not implemented

---

## MVP Use Case

**Scenario:** The user wants all "definitions" from the `constraints` section of `example.md`.

1. Run the CLI for targeted H2 ingestion (optional if already ingested):
```bash
python main.py example.md --h2 constraints
```
2. Query Python API for filtered data:
```python
rows = query(db, h2='constraints', type_filter='definition')
```
3. The returned rows contain only the relevant definitions with provenance info.

**Expected Behavior:**
- Only rows matching H2 `constraints` and type `definition` are returned.
- Each row includes `row_id`, original file, line number, and ingestion timestamp.
- Malformed rows are reported in the CLI but skipped in query results.

---

## Minimal LLM Knowledge

- The tool exposes **H2 sections** and **type filters** as query parameters.
- Ingested rows include **provenance fields** (`file`, `line_no`, `ingest_ts`) for context.
- Queries always return lists of tuples with a predictable schema.
- CLI commands are sufficient to ingest new data; the LLM only needs to know what section and type to retrieve.

This guide ensures that an LLM or automated process can interact with `md_ledger_tool` effectively without assuming unnecessary context.

