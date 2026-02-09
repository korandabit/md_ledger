# MD Ledger Tool

[![GitHub](https://img.shields.io/badge/github-korandabit/md__ledger-blue)](https://github.com/korandabit/md_ledger.git)

Token-efficient, structure-aware Markdown navigation and table management tool. Provides persistent header indexing with automatic freshness, enabling targeted section access and content search with full provenance.

## Why Use This?

- **53-92% token savings** - Navigate directly to relevant sections instead of reading entire files
- **Structure-aware search** - Find content with full section hierarchy context
- **Zero maintenance** - Auto-reindexes when files change (< 150ms overhead)
- **Persistent knowledge** - Header index survives across sessions
- **Full provenance** - Track every table row back to source file, line, and section
- **Bidirectional sync** - Update markdown files and database stays in sync

Perfect for LLM workflows, documentation navigation, and maintaining large markdown knowledge bases.

---

## Quick Start

```bash
# Install
pip install -e .

# Index your markdown files
md-ledger index . --recursive

# Find a section
md-ledger find-section "Installation"
# → README.md:23-45 (H2 "Installation")

# Search content with context
md-ledger find-content "authentication" --context 2

# View document structure
md-ledger headers README.md
```

Get help anytime:
```bash
md-ledger --help              # Overview and examples
md-ledger <command> --help    # Detailed command help
```

---

## Common Workflows

### Navigate Large Documentation

```bash
# Index project once
md-ledger index . --recursive

# Explore structure
md-ledger headers ARCHITECTURE.md

# Find specific section
md-ledger find-section "API Reference"
# → ARCHITECTURE.md:150-200 (H2 "API Reference")

# Read just that section with your tools
# Read(file="ARCHITECTURE.md", offset=150, limit=50)
```

**Token savings:** 89-99% vs reading full file

### Search Across Project

```bash
# Find all mentions with section context
md-ledger find-content "authentication" --context 2

# Output shows:
#   auth.md:45
#     Section: Security > User Authentication > Implementation
#     Range: lines 40-60
#     Context: [matching lines with ±2 lines]

# Limit to specific file
md-ledger find-content "pipeline" --file architecture.md
```

**Token savings:** 40-78% vs grep + multiple reads

### Manage Structured Table Data

```bash
# Ingest pipe-delimited tables from markdown
md-ledger ingest constraints.md --full

# Query specific sections/types
md-ledger query ledger.db --h2 constraints --type definition

# Update source markdown (syncs to DB automatically)
md-ledger update ROW_ID "new content"
```

**Benefit:** Full provenance - every row knows its file, line, section

---

## Installation

```bash
# From GitHub
git clone https://github.com/korandabit/md_ledger.git
cd md_ledger
pip install -e .
```

**Requirements:**
- Python 3.10+
- No external dependencies (stdlib only: sqlite3, pathlib, argparse)

**Testing (optional):**
```bash
pip install pytest
pytest
```

---

## CLI Commands

Each command has detailed help with examples:

```bash
md-ledger --help              # See all commands
md-ledger <command> --help    # Command-specific help
```

### Header Navigation

**index** - Index markdown files for structure-aware navigation
```bash
md-ledger index .              # Current directory
md-ledger index . --recursive  # Include subdirectories
md-ledger index README.md      # Single file
```

**headers** - Display complete header hierarchy
```bash
md-ledger headers README.md
# Shows full H1-H6 tree with line ranges
```

**find-section** - Find sections by header name
```bash
md-ledger find-section "Installation"
md-ledger find-section "API" --file README.md
```

**find-content** - Search content with section context
```bash
md-ledger find-content "authentication"
md-ledger find-content "config" --context 3 --file arch.md
```

### Table Management

**ingest** - Import pipe-delimited tables from markdown
```bash
md-ledger ingest data.md --full           # All tables
md-ledger ingest data.md --h2 constraints # Specific section
md-ledger data.md                         # Implicit ingest
```

**query** - Query ingested table data
```bash
md-ledger query ledger.db --h2 constraints --type definition
```

**update** - Update table row in source markdown
```bash
md-ledger update ROW_ID "new content"
md-ledger update ROW_ID "text" --db custom.db
```

### Python API

```python
from md_ledger_tool.main import init_db, find_content, query_headers

db = init_db()

# Search with section context
results = find_content(db, "pipeline", context_lines=2)
for file, line, text, section in results:
    if section:
        header, level, start, end, path = section
        print(f"{file}:{line} in '{path}' (lines {start}-{end})")

# Get header tree (auto-reindexes if stale)
headers = query_headers(db, "README.md")
for h in headers:
    id, file, text, level, start, end, parent = h
    print(f"H{level} '{text}' lines {start}-{end}")

# Query table data
rows = query(db, h2='constraints', type_filter='definition')
```

---

## Database Structure

Three tables in `ledger.db`:

**header_index** - Document structure (H1-H6 hierarchy)
- File, header text, level, line range, parent relationships
- Tracks file mtime for automatic staleness detection
- Indexed on header_text and file for fast search

**ledger** - Table data rows with full provenance
- row_id, h2 section, text, source, type
- File path, line number, status, timestamp
- Each row traceable to exact source location

**table_config** - Table metadata
- Column count, line ranges per H2 section
- Enables validation and structural queries

---

## Best Practices & Limitations

### Best Practices

- **Index once per project** - Run `md-ledger index . --recursive` on first use
- **Trust auto-reindex** - Files automatically reindex when modified (< 150ms)
- **Use targeted reads** - Combine md-ledger with offset/limit reads for token efficiency
- **Check structure first** - Use `headers` before deep reading to understand layout
- **Reset on schema changes** - Delete `ledger.db` and re-ingest if structure changes

### Limitations

**Table ingestion:**
- Assumes pipe-delimited tables under H2 (`##`) headers
- Any line with pipes is treated as data (no header row detection)
- Code fences are skipped but don't protect tables inside them
- Last ingestion wins for duplicate row_ids (no version history)

**Header navigation:**
- Only indexes standard markdown headers (`#` through `######`)
- Requires files to be indexed before querying
- Line ranges assume files don't change drastically between index and read

---

## Development Notes

This tool was developed in three phases:

**Phase 1: Table Parsing**
- Pipe-delimited table ingestion with provenance tracking
- Bidirectional file-DB sync for updates
- Dynamic table configuration capture

**Phase 2: Header Navigation**
- Project-wide header indexing (H1-H6)
- Section search and targeted retrieval
- Hierarchy tracking with parent-child relationships

**Phase 3: Auto-Reindexing**
- Mtime-based staleness detection
- Lazy reindex on query (< 150ms overhead)
- Zero-maintenance automatic freshness

Each phase built on the previous, resulting in a cohesive tool for markdown navigation and table management optimized for LLM workflows.

---

## Testing

Run test suite:
```bash
pytest
```

Tests cover:
- Ingestion logic and edge cases
- Header parsing and indexing
- Update synchronization
- Auto-reindexing behavior
- CLI help functionality

---

## Summary

MD Ledger Tool provides **token-efficient, structure-aware access** to markdown files with **automatic freshness management** and **full provenance tracking**. Designed for LLM workflows, documentation navigation, and maintaining large markdown knowledge bases with minimal token overhead and zero maintenance burden.
