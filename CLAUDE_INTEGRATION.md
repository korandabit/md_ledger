# Claude Code Integration Guide

This guide shows how to configure Claude Code to automatically use `md_ledger_tool` for large Markdown files, preventing wasteful token usage from reading entire files.

---

## Problem Statement

When working with large Markdown files (hundreds or thousands of lines), using standard Read/Edit tools:
- Wastes tokens loading entire files when only specific sections are needed
- Slows down operations
- Makes targeted updates difficult

`md_ledger_tool` solves this by:
- **Phase 1:** Ingesting tables into SQLite with H2 section indexing and row-level queries
- **Phase 2:** Indexing header structure (H1-H6) for targeted section reads
- Enabling surgical updates with provenance tracking

---

## Automatic Integration via MEMORY.md

To make Claude Code automatically use md-ledger for large Markdown files, add this protocol to your project's `MEMORY.md`:

```markdown
# MD Ledger Tool Protocol

## Large Markdown File Handling

**Before reading any .md file**: Check line count first.

```bash
wc -l file.md
```

**If 50+ lines:**
1. **First, try header indexing** (works for any markdown):
   ```bash
   md-ledger index file.md
   md-ledger find-section "Installation"
   # Output: file.md:23-45
   # Then: Read(file.md, offset=23, limit=22)
   ```

2. **For table-based files**, use table ingestion:
   ```bash
   md-ledger ingest file.md --full
   ```
   Tool reports tables found in output

3. **If tables found**, use md-ledger for all queries/updates:

   **Query example** (get all definitions from constraints section):
   ```python
   from md_ledger_tool.main import init_db, query

   db = init_db()
   rows = query(db, h2='constraints', type_filter='definition')
   for row in rows:
       print(f"{row[0]}: {row[2]}")  # row_id: text
   ```

   **Update example** (modify a specific row):
   ```bash
   md-ledger update C171 "Updated content here"
   ```
   Or via Python:
   ```python
   from md_ledger_tool.apply_update import apply_update

   apply_update(row_id='C171', new_text='Updated content here')
   ```

4. **If no tables found**, header indexing provides navigation

**If < 50 lines:** Use Read tool normally

---

**Note**: Row schema is `(row_id, h2, text, src, type, file, line_no, status, ingest_ts)`
```

---

## Why This Works

- **MEMORY.md is loaded in every Claude Code session** (first 200 lines are included in system prompt)
- Creates a **preventative protocol** that stops wasteful Reads before they happen
- **Adaptive**: Tool self-validates by reporting tables found during ingestion
- **Fail-safe**: Falls back to Read if file doesn't match expected structure

---

## Workflow Example

**User task**: "Update definition D42 in constraints section of constraint_ledger.md"

**Without md-ledger** (wasteful):
```
1. Read entire 2000-line file → 50k+ tokens
2. Find section manually
3. Edit with string replacement
```

**With md-ledger** (targeted):
```
1. Check: wc -l constraint_ledger.md → 2000 lines
2. Ingest: md-ledger ingest constraint_ledger.md --full → Reports tables found
3. Query: query(db, h2='constraints', type_filter='definition') → Get D42 row
4. Update: md-ledger update D42 "new text" → Surgical change
```

**Token savings**: ~48k tokens, instant targeted access

---

## Customization

Adjust the line threshold (default: 50) based on your needs:
- **Lower threshold (30-40)**: More aggressive token saving
- **Higher threshold (100+)**: Only use for very large files

The tool handles validation automatically - if no tables are found, Claude falls back to normal Read operations.

---

## Additional Resources

- [CLAUDE.md](./CLAUDE.md) - Full tool affordances and API reference
- [README.md](./README.md) - Installation and feature overview
- Tool repository: https://github.com/korandabit/md_ledger.git
