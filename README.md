# MD Ledger Tool

[![GitHub](https://img.shields.io/badge/github-korandabit/md__ledger-blue)](https://github.com/korandabit/md_ledger.git)

Ingest Markdown tables into SQLite with full provenance tracking (file, line, section). Query by H2/type, update with file-DB sync. Built for selective retrieval in LLM workflows.

---

## Features

- **Targeted H2 ingestion:** Ingest only specific H2 sections from Markdown files.
- **Full document ingestion:** Ingest all tables from a Markdown file.
- **Provenance tracking:** Each row stores file name, line number, H2, ingestion timestamp, and status.
- **Source file updates:** Modify ingested rows in the original Markdown using provenance data.
- **Fail-fast validation:** Detects malformed rows to prevent silent errors.
- **Persistent DB:** All ingested data is stored in `ledger.db` between sessions.
- **Dynamic table configuration:** Automatically captures column count and line ranges for each H2.
- **Minimal token exposure for LLMs:** Only retrieve necessary rows to feed into language models.

---

## Installation

**From GitHub:**
```bash
git clone https://github.com/korandabit/md_ledger.git
cd md_ledger
pip install -e .
```

**Requirements:**
- Python 3.10+
- No external dependencies (uses stdlib: sqlite3, pathlib, argparse, datetime)

**Optional (for testing):**
```bash
pip install pytest
```

**Setup:**
- Place Markdown files in the `md/` folder
- Run `md-ledger ingest yourfile.md --full` to initialize

---

## CLI Usage

### Ingesting files

**Full ingest of a file:**
```bash
md-ledger ingest example.md --full
# or implicit: md-ledger example.md
```

**Targeted H2 ingest:**
```bash
md-ledger ingest example.md --h2 constraints
```

**Output:**
- Prints number of rows ingested per H2.
- Reports errors for malformed rows.

### Querying data

From Python:
```python
from md_ledger_tool.main import init_db, query

db = init_db()
rows = query(db, h2='constraints', type_filter='definition')
for r in rows:
    print(r)
```

From SQLite CLI:
```bash
sqlite3 ledger.db
.tables
SELECT * FROM ledger WHERE h2='constraints';
```

### Updating source Markdown

**Via CLI:**
```bash
md-ledger update C171 "Updated content here"
# or with custom DB:
md-ledger update C171 "New text" --db custom.db
```

**Via Python:**
```python
from md_ledger_tool.apply_update import apply_update

apply_update(row_id='C171', new_text='Updated content here')
```

**Behavior:**
- Updates both the source Markdown file AND the database row
- Only modifies the `text` column (2nd column)
- Updates `ingest_ts` to current timestamp and sets `status='updated'`
- Fails fast if row_id, file, or line number is invalid
- Returns exit code 1 on error (CLI), raises exception (Python)

---

## Database Structure

**ledger** table:
- `row_id` (TEXT PRIMARY KEY)
- `h2` (TEXT)
- `text` (TEXT)
- `src` (TEXT)
- `type` (TEXT)
- `file` (TEXT)
- `line_no` (INTEGER)
- `status` (TEXT, default 'clean')
- `ingest_ts` (TEXT, UTC timestamp)

**table_config** table:
- `file_name` (TEXT)
- `h2` (TEXT)
- `col_count` (INTEGER)
- `line_start` (INTEGER)
- `line_end` (INTEGER)

---

## Provenance & Versioning

- Each row tracks **file**, **line number**, **H2 section**, **status**, and **ingest timestamp**.
- **Duplicate handling**: `INSERT OR REPLACE` means last ingestion wins for same `row_id`
- **Update tracking**:
  - Ingested rows: `status='clean'`, `ingest_ts` = ingestion time
  - Updated rows: `status='updated'`, `ingest_ts` = last update time
- Version history beyond latest timestamp not currently implemented
- Designed to support LLM workflows with minimal token exposure.

---

## Best Practices

- Always keep Markdown files in the `md/` folder for consistent ingestion.
- Use targeted H2 ingestion when feeding data to LLMs to reduce token usage.
- Periodically inspect `ledger.db` with SQLite CLI or Python queries for validation.
- If schemas change or errors occur, delete `ledger.db` and rerun ingestion to reset.

---

## Limitations

- Assumes tables are **pipe-delimited**, H2 headers are `##` level.
- Any line with pipes is treated as data; no header row detection or column name storage.
- Lines without pipes (prose, headers) are skipped entirely.
- Code fence delimiters (```) are skipped but tables inside code blocks are still ingested.
- No full historical versioning beyond the latest ingestion timestamp.
- Duplicate `row_id` entries use `INSERT OR REPLACE` (last ingestion wins).

---

## Testing

Run automated tests:
```bash
pytest
```
- Validates ingestion logic and edge cases.
- Requires `pytest`.

---

## Summary

MD Ledger Tool provides a **robust, minimal, and traceable system** for ingesting Markdown tables, tracking provenance, and selectively exposing data for downstream applications, including LLM-assisted reasoning. Designed to balance **control, reliability, and usability** for large or curated Markdown knowledgebases.

