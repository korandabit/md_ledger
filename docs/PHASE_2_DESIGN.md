# Phase 2: Header-Aware Navigation

## Overview

Extend `md_ledger_tool` to index Markdown header structure (H1-H6) with line boundaries, enabling:
- Project-wide header tree awareness
- Targeted section reads without full file parsing
- Token-efficient navigation across multiple documents

---

## Problem Statement

**Current limitations:**
- Claude must Grep for headers and manually calculate section boundaries
- No persistent awareness of document structure across sessions
- Repeated parsing wastes tokens on 50+ line docs touched 4+ times per session
- No project-wide "macro awareness" of all Markdown files

**Target use case:**
- Moderate-sized docs (50-500 lines) with 2-3 header levels
- READMEs, changelogs, documentation, design docs
- Multiple accesses per dev session (4+ touches)
- Need quick navigation: "Update Installation section" → know exactly where it is

---

## Core Features

### 1. Project-Wide Indexing

**Command:**
```bash
md-ledger index <path>
md-ledger index .                    # Current directory
md-ledger index . --recursive        # Recursive scan
md-ledger index specific-file.md     # Single file
```

**Behavior:**
- Scans for `*.md` files
- Parses header hierarchy (H1-H6)
- Calculates line boundaries for each section
- Stores in `header_index` table
- Reports: "Indexed 12 files, 47 headers"

### 2. Header Tree Query

**Command:**
```bash
md-ledger headers <file>
md-ledger headers README.md
```

**Output:**
```
README.md:
  H1 "MD Ledger Tool" lines 1-8
  H2 "Features" lines 9-19
  H2 "Installation" lines 20-43
    H3 "From GitHub" lines 24-29
    H3 "Requirements" lines 30-35
  H2 "Usage" lines 44-120
    H3 "Ingesting files" lines 48-64
```

### 3. Section Finder

**Command:**
```bash
md-ledger find-section "Installation"
md-ledger find-section "Installation" --file README.md
```

**Output:**
```
README.md:20-43 (H2 "Installation")
```

**Python API:**
```python
from md_ledger_tool.headers import find_section

result = find_section(db, "Installation")
# Returns: {'file': 'README.md', 'level': 2, 'start': 20, 'end': 43}
```

### 4. Integration with Existing Workflow

**Enhanced MEMORY.md protocol:**
```markdown
## Large Markdown File Protocol

Before reading any .md file:
1. Check if indexed: `md-ledger headers file.md`
2. If indexed:
   - Query for target section
   - Read only that section with offset/limit
3. If not indexed and 50+ lines:
   - Run `md-ledger index file.md`
   - Then query as above
4. If < 50 lines: Use Read normally
```

---

## Database Schema

**New table: `header_index`**
```sql
CREATE TABLE IF NOT EXISTS header_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,                -- Relative path: 'README.md'
    header_text TEXT NOT NULL,         -- "Installation"
    level INTEGER NOT NULL,            -- 1-6 (H1-H6)
    line_start INTEGER NOT NULL,       -- Section start line
    line_end INTEGER NOT NULL,         -- Section end line (calculated)
    parent_id INTEGER,                 -- FK to parent header (hierarchy)
    indexed_ts TEXT NOT NULL,          -- UTC timestamp
    UNIQUE(file, line_start)
);

CREATE INDEX idx_header_search ON header_index(header_text);
CREATE INDEX idx_header_file ON header_index(file);
```

**Example rows:**
```
| id | file       | header_text  | level | line_start | line_end | parent_id | indexed_ts          |
|----|------------|--------------|-------|------------|----------|-----------|---------------------|
| 1  | README.md  | MD Ledger    | 1     | 1          | 8        | NULL      | 2026-02-08T10:00:00 |
| 2  | README.md  | Features     | 2     | 9          | 19       | 1         | 2026-02-08T10:00:00 |
| 3  | README.md  | Installation | 2     | 20         | 43       | 1         | 2026-02-08T10:00:00 |
| 4  | README.md  | From GitHub  | 3     | 24         | 29       | 3         | 2026-02-08T10:00:00 |
```

---

## Implementation Plan

### Step 1: Header Parser Module

**New file: `md_ledger_tool/header_parser.py`**

**Functions:**
```python
def parse_headers(file_path: str) -> List[HeaderNode]:
    """
    Parse markdown file, extract headers with line numbers.
    Returns list of HeaderNode(text, level, line_start).
    """

def calculate_boundaries(headers: List[HeaderNode]) -> List[HeaderSection]:
    """
    Calculate line_end for each header section.
    Rules:
    - Section ends where next same-or-higher level header starts
    - Last section ends at EOF
    Returns HeaderSection(text, level, line_start, line_end, parent_id).
    """

def build_hierarchy(sections: List[HeaderSection]) -> List[HeaderSection]:
    """
    Assign parent_id based on nesting level.
    H3 under H2 gets parent_id of that H2.
    """
```

### Step 2: Index Command

**Extend `md_ledger_tool/main.py`:**

```python
def index_command(path: str, recursive: bool = False):
    """
    Index markdown files at path.
    If recursive, scan subdirectories.
    """
    files = glob_markdown_files(path, recursive)
    db = init_db()

    total_headers = 0
    for file in files:
        headers = parse_headers(file)
        sections = calculate_boundaries(headers)
        sections = build_hierarchy(sections)

        for section in sections:
            insert_header(db, file, section)

        total_headers += len(sections)

    print(f"Indexed {len(files)} files, {total_headers} headers")
```

### Step 3: Query Commands

**Add to `md_ledger_tool/main.py`:**

```python
def headers_command(file: str):
    """Display header tree for file."""
    db = init_db()
    tree = query_headers(db, file)
    print_tree(tree)

def find_section_command(query: str, file: str = None):
    """Find section by name across files."""
    db = init_db()
    results = find_section(db, query, file)
    for r in results:
        print(f"{r['file']}:{r['line_start']}-{r['line_end']} (H{r['level']} \"{r['header_text']}\")")
```

### Step 4: CLI Integration

**Extend `argparse` in `main.py`:**

```python
subparsers.add_parser('index', help='Index markdown headers')
subparsers.add_parser('headers', help='Show header tree')
subparsers.add_parser('find-section', help='Find section by name')
```

### Step 5: Schema Migration

**Add to `md_ledger_tool/schema.py`:**

```python
def create_header_index_table(db):
    """Create header_index table if not exists."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS header_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file TEXT NOT NULL,
            header_text TEXT NOT NULL,
            level INTEGER NOT NULL,
            line_start INTEGER NOT NULL,
            line_end INTEGER NOT NULL,
            parent_id INTEGER,
            indexed_ts TEXT NOT NULL,
            UNIQUE(file, line_start)
        )
    """)
    # Create indexes...
```

---

## Testing Strategy

**Unit tests (`tests/test_header_parser.py`):**
- Parse simple header structure (H1, H2, H3)
- Calculate boundaries correctly (last section, nested sections)
- Build hierarchy (parent_id assignment)
- Handle edge cases (no headers, duplicate names, EOF)

**Integration tests (`tests/test_index_command.py`):**
- Index single file
- Index directory (recursive/non-recursive)
- Query indexed headers
- Find section by name

**Test fixtures:**
- `tests/fixtures/sample_doc.md` (structured doc with H1-H3)
- `tests/fixtures/flat_doc.md` (only H2s)
- `tests/fixtures/no_headers.md` (plain text)

---

## Documentation Updates

**Files to update:**
1. **README.md**: Add Phase 2 features section
2. **CLAUDE.md**: Update with header indexing commands
3. **CLAUDE_INTEGRATION.md**: Enhance MEMORY.md template with header queries

---

## Success Criteria

- [ ] Index command parses headers and stores in DB
- [ ] Query commands return correct line ranges
- [ ] Integration with existing table parsing (no conflicts)
- [ ] MEMORY.md protocol updated for header-aware reads
- [ ] Tests achieve 90%+ coverage on new modules
- [ ] Documentation complete and accurate

---

## Token Savings Example

**Without header indexing:**
```
User: "Update Installation section in README.md"
1. Read README.md (300 lines) → 7.5k tokens
2. Find section manually
3. Edit
Total: ~7.5k tokens
```

**With header indexing:**
```
User: "Update Installation section in README.md"
1. Query: find-section "Installation" → README.md:20-43
2. Read(README.md, offset=20, limit=23) → 575 tokens
3. Edit
Total: ~600 tokens (92% savings)
```

**Per-session impact:**
- 4 touches × 7k saved = **28k tokens saved per dev session**
- Across 10 files × 5 sessions = **1.4M tokens saved per project**

---

## Migration Path

**For existing users:**
1. Pull latest version
2. Run `md-ledger index .` in project root
3. Update MEMORY.md with new protocol (optional but recommended)
4. Existing table ingestion continues to work unchanged

**No breaking changes.**

---

## Future Considerations (Phase 3)

See `PHASE_3_PLAN.md` for:
- Auto-reindexing on file changes
- Watch mode for live updates
- Diff-based incremental indexing
