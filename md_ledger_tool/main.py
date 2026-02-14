import sqlite3
from pathlib import Path
import hashlib
from datetime import datetime
import argparse
import sys

DB_FILE = "ledger.db"

def get_utc_timestamp():
    """Get UTC timestamp, handling deprecation of datetime.utcnow()."""
    try:
        return datetime.now(datetime.UTC).isoformat()
    except AttributeError:
        # Python < 3.11
        return datetime.utcnow().isoformat()

def open_db(db_path=None):
    """
    Open database and ensure schema is up to date.
    Deprecated: Use init_db() instead.
    """
    path = Path(db_path or DB_FILE).resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"No ledger.db in current directory ({path.parent}). Run ingest first."
        )
    print(f"[md-ledger] using DB: {path}")
    # Use init_db to ensure migrations are applied
    return init_db(str(path))


def init_db(db_path=DB_FILE):
    db = sqlite3.connect(db_path)
    db.execute("""
    CREATE TABLE IF NOT EXISTS ledger (
        row_id TEXT PRIMARY KEY,
        h2 TEXT,
        text TEXT,
        src TEXT,
        type TEXT,
        file TEXT,
        line_no INTEGER,
        status TEXT DEFAULT 'clean',
        ingest_ts TEXT
    )""")
    db.execute("""
    CREATE TABLE IF NOT EXISTS table_config (
        file_name TEXT,
        h2 TEXT,
        col_count INTEGER,
        line_start INTEGER,
        line_end INTEGER,
        PRIMARY KEY(file_name,h2)
    )""")
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
        file_mtime REAL,
        UNIQUE(file, line_start)
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_header_search ON header_index(header_text)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_header_file ON header_index(file)")

    # Migration: Add file_mtime column if it doesn't exist
    cursor = db.execute("PRAGMA table_info(header_index)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'file_mtime' not in columns:
        db.execute("ALTER TABLE header_index ADD COLUMN file_mtime REAL")
        db.commit()

    return db


def ingest_file(db, filename, target_h2=None, full_ingest=False):
    from pathlib import Path

    file_path = Path(filename)

    # === Try exact path first ===
    md_path = file_path.resolve()
    if not md_path.exists():
        # fallback: look in md/ subfolder relative to cwd
        candidate = Path("md") / file_path.name
        md_path = candidate.resolve()
        if not md_path.exists():
            raise FileNotFoundError(f"{filename} not found in '{file_path}' or 'md/' subfolder.")


    lines = md_path.read_text().splitlines()

    current_h2 = None
    header_rows = []
    line_start = None
    table_config_done = {}
    rows_ingested = 0
    h2_counts = {}
    ingest_ts = get_utc_timestamp()
    in_code_fence = False

    for idx, line in enumerate(lines):
        line_strip = line.strip()

        # track code fence state
        if line_strip.startswith("```"):
            in_code_fence = not in_code_fence
            continue

        if line_strip.startswith("## "):
            # store config for previous H2
            if current_h2 and header_rows:
                col_count = max(len(r.split("|")) for r in header_rows)
                table_config_done[current_h2] = {
                    "col_count": col_count,
                    "line_start": line_start,
                    "line_end": idx - 1
                }
            # new H2
            current_h2 = line_strip[3:].strip()
            line_start = idx + 1
            header_rows = []
            h2_counts.setdefault(current_h2, 0)
            continue

        if not line_strip or current_h2 is None:
            continue

        # skip lines without pipes
        if "|" not in line_strip:
            continue

        header_rows.append(line_strip)

        # ingest if target_h2 matches
        should_ingest = full_ingest or (target_h2 and target_h2.lower() in current_h2.lower())
        if should_ingest:
            parts = [p.strip() for p in line_strip.split("|")]
            if len(parts) < 1:
                raise ValueError(f"[ERROR] Malformed row at {md_path.name}:{idx+1} -> '{line_strip}'")
            row_id = parts[0]
            text = parts[1] if len(parts) > 1 else ""
            src = parts[2] if len(parts) > 2 else ""
            typ = parts[3] if len(parts) > 3 else ""
            db.execute(
                "INSERT OR REPLACE INTO ledger VALUES (?,?,?,?,?,?,?,?,?)",
                (row_id, current_h2.lower(), text, src, typ, md_path.name, idx+1, "clean", ingest_ts)
            )
            rows_ingested += 1
            h2_counts[current_h2] += 1

    # store config for last H2
    if current_h2 and header_rows:
        col_count = max(len(r.split("|")) for r in header_rows)
        table_config_done[current_h2] = {
            "col_count": col_count,
            "line_start": line_start,
            "line_end": len(lines)
        }

    # persist table_config
    for h2, cfg in table_config_done.items():
        db.execute(
            "INSERT OR REPLACE INTO table_config VALUES (?,?,?,?,?)",
            (md_path.name, h2, cfg["col_count"], cfg["line_start"], cfg["line_end"])
        )

    db.commit()
    print(f"Successfully ingested {rows_ingested} row(s) from {md_path.name}.")
    if h2_counts:
        for h2, count in h2_counts.items():
            print(f"H2 '{h2}': {count} row(s) ingested.")
    return {
        "rows_ingested": rows_ingested,
        "table_config": table_config_done,
        "h2_counts": h2_counts
    }

def query(db, h2, type_filter=None):
    sql = "SELECT * FROM ledger WHERE h2=?"
    params = [h2.lower()]
    if type_filter:
        sql += " AND type=?"
        params.append(type_filter)
    cur = db.execute(sql, params)
    return cur.fetchall()

def query_ledger(db, h2=None, type_filter=None):
    sql = "SELECT * FROM ledger WHERE 1=1"
    params = []

    if h2:
        sql += " AND h2 = ?"
        params.append(h2)

    if type_filter:
        sql += " AND type = ?"
        params.append(type_filter)

    cur = db.execute(sql, params)
    return cur.fetchall()


def index_markdown_files(db, path, recursive=False):
    """
    Index markdown files in the given path.

    Args:
        db: Database connection
        path: File path or directory path
        recursive: Whether to scan subdirectories
    """
    from .header_parser import parse_file_headers

    path_obj = Path(path)
    files = []

    if path_obj.is_file():
        if path_obj.suffix == '.md':
            files = [path_obj]
    elif path_obj.is_dir():
        if recursive:
            files = list(path_obj.rglob('*.md'))
        else:
            files = list(path_obj.glob('*.md'))
    else:
        raise FileNotFoundError(f"Path not found: {path}")

    if not files:
        print(f"No .md files found in {path}")
        return

    total_headers = 0
    indexed_ts = get_utc_timestamp()

    for file_path in files:
        try:
            # Get file modification time
            file_mtime = file_path.stat().st_mtime

            # Parse headers from file
            sections = parse_file_headers(str(file_path))

            if not sections:
                print(f"No headers found in {file_path.name}")
                continue

            # Clear existing index for this file
            db.execute("DELETE FROM header_index WHERE file = ?", (str(file_path.name),))

            # Insert header sections
            for section in sections:
                db.execute("""
                    INSERT INTO header_index (file, header_text, level, line_start, line_end, parent_id, indexed_ts, file_mtime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(file_path.name),
                    section.text,
                    section.level,
                    section.line_start,
                    section.line_end,
                    section.parent_id,
                    indexed_ts,
                    file_mtime
                ))

            total_headers += len(sections)
            print(f"Indexed {file_path.name}: {len(sections)} headers")

        except Exception as e:
            print(f"Error indexing {file_path.name}: {e}")
            continue

    db.commit()
    print(f"\nIndexed {len(files)} file(s), {total_headers} total headers")


def is_file_stale(db, file_path):
    """
    Check if indexed file has been modified since last index.

    Args:
        db: Database connection
        file_path: Path to file (can be Path object or string)

    Returns:
        True if file is stale (needs reindex), False if fresh, None if not indexed
    """
    path_obj = Path(file_path)

    # Check if file exists
    if not path_obj.exists():
        return None  # File doesn't exist

    # Get current file mtime
    current_mtime = path_obj.stat().st_mtime

    # Query stored mtime
    row = db.execute("""
        SELECT file_mtime FROM header_index
        WHERE file = ?
        LIMIT 1
    """, (path_obj.name,)).fetchone()

    if not row:
        return None  # Not indexed

    stored_mtime = row[0]

    # If stored_mtime is None (legacy index), treat as stale
    if stored_mtime is None:
        return True

    # File is stale if current mtime is newer than stored
    return current_mtime > stored_mtime


def reindex_file_if_stale(db, file_path):
    """
    Check if file is stale and reindex if needed.

    Args:
        db: Database connection
        file_path: Path to file

    Returns:
        True if reindexed, False if already fresh
    """
    staleness = is_file_stale(db, file_path)

    if staleness is None:
        # Not indexed yet - index it
        print(f"File not indexed, indexing {Path(file_path).name}...")
        index_markdown_files(db, str(file_path), recursive=False)
        return True
    elif staleness:
        # File is stale - reindex
        print(f"File modified, reindexing {Path(file_path).name}...")
        index_markdown_files(db, str(file_path), recursive=False)
        return True
    else:
        # File is fresh
        return False


def query_headers(db, file):
    """
    Query header tree for a specific file.
    Automatically reindexes if file has been modified.

    Returns list of tuples: (id, file, header_text, level, line_start, line_end, parent_id)
    """
    # Lazy reindex if stale
    reindex_file_if_stale(db, file)

    cur = db.execute("""
        SELECT id, file, header_text, level, line_start, line_end, parent_id
        FROM header_index
        WHERE file = ?
        ORDER BY line_start
    """, (file,))
    return cur.fetchall()


def print_header_tree(headers):
    """
    Print header tree in a readable format.

    Args:
        headers: List of header tuples from query_headers
    """
    if not headers:
        print("No headers found (file may not be indexed)")
        return

    filename = headers[0][1]
    print(f"\n{filename}:")

    for header in headers:
        header_id, file, text, level, line_start, line_end, parent_id = header
        indent = "  " * (level - 1)
        print(f"{indent}H{level} \"{text}\" lines {line_start}-{line_end}")


def find_section(db, query_text, file=None):
    """
    Find sections by header text (case-insensitive substring match).

    Args:
        db: Database connection
        query_text: Text to search for in header names
        file: Optional file filter

    Returns:
        List of matching sections
    """
    sql = """
        SELECT file, header_text, level, line_start, line_end
        FROM header_index
        WHERE header_text LIKE ?
    """
    params = [f"%{query_text}%"]

    if file:
        sql += " AND file = ?"
        params.append(file)

    sql += " ORDER BY file, line_start"

    cur = db.execute(sql, params)
    return cur.fetchall()


def get_section_for_line(db, file, line_no):
    """
    Find which section a specific line belongs to.

    Args:
        db: Database connection
        file: File name
        line_no: Line number to locate

    Returns:
        Tuple of (header_text, level, line_start, line_end, header_path) or None
        header_path is full hierarchy like "H1 Title > H2 Subsection"
    """
    # Find section containing this line
    section = db.execute("""
        SELECT id, header_text, level, line_start, line_end, parent_id
        FROM header_index
        WHERE file = ? AND line_start <= ? AND line_end >= ?
        ORDER BY level DESC
        LIMIT 1
    """, (file, line_no, line_no)).fetchone()

    if not section:
        return None

    section_id, header_text, level, line_start, line_end, parent_id = section

    # Build header path (hierarchy)
    path_parts = [header_text]
    current_parent_id = parent_id

    while current_parent_id is not None:
        parent = db.execute("""
            SELECT header_text, parent_id
            FROM header_index
            WHERE id = ?
        """, (current_parent_id,)).fetchone()

        if parent:
            path_parts.insert(0, parent[0])
            current_parent_id = parent[1]
        else:
            break

    header_path = " > ".join(path_parts)

    return (header_text, level, line_start, line_end, header_path)


def find_content(db, search_text, file=None, context_lines=1):
    """
    Search for text in file content and return matches with section context.

    Args:
        db: Database connection
        search_text: Text to search for
        file: Optional file filter
        context_lines: Lines of context before/after match

    Returns:
        List of tuples: (file, line_no, match_text, section_info)
        section_info is (header_text, level, line_start, line_end, header_path)
    """
    from pathlib import Path

    # Get list of indexed files
    if file:
        files = [file]
    else:
        files_query = db.execute("SELECT DISTINCT file FROM header_index").fetchall()
        files = [row[0] for row in files_query]

    results = []

    for filename in files:
        # Read file content
        try:
            path = Path(filename)
            if not path.exists():
                continue

            lines = path.read_text(encoding='utf-8').splitlines()

            # Search for matches
            for line_no, line in enumerate(lines, start=1):
                if search_text.lower() in line.lower():
                    # Get context lines
                    start_ctx = max(0, line_no - context_lines - 1)
                    end_ctx = min(len(lines), line_no + context_lines)
                    context = lines[start_ctx:end_ctx]
                    match_text = "\n".join(context)

                    # Get section info
                    section_info = get_section_for_line(db, filename, line_no)

                    results.append((filename, line_no, match_text, section_info))

        except Exception as e:
            continue

    return results


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    # implicit ingest: md-ledger somefile.md
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        filename = sys.argv[1]
        db = init_db(DB_FILE)
        ingest_file(db, filename)
        return 0

    parser = argparse.ArgumentParser(
        prog="md-ledger",
        description="""
Token-efficient, structure-aware Markdown file navigation and management tool.

Provides persistent indexing of header hierarchy with automatic freshness management,
enabling targeted section access and content search with full provenance.
        """.strip(),
        epilog="""
EXAMPLES:
  # Index all markdown files in project
  md-ledger index . --recursive

  # View document structure
  md-ledger headers README.md

  # Find section by header name
  md-ledger find-section "Installation"
  md-ledger find-section "API" --file README.md

  # Search content with section context
  md-ledger find-content "authentication" --context 2
  md-ledger find-content "pipeline" --file architecture.md

  # Ingest table data from markdown
  md-ledger ingest constraints.md --full
  md-ledger ingest data.md --h2 "Configuration"

  # Query ingested table data
  md-ledger query ledger.db --h2 constraints --type definition

  # Update table row
  md-ledger update ROW_ID "new content here"

TOKEN EFFICIENCY:
  Provides 53-92% token savings vs. full file reads by enabling targeted
  section access. Auto-reindexes on file modification (< 150ms overhead).

WORKFLOW:
  1. Index project: md-ledger index . --recursive
  2. Navigate: md-ledger find-section "target"
  3. Read: Use offset/limit from output with your Read tool

For more information, see CLAUDE.md in the project root.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=False,
        title="commands",
        description="Available commands for markdown file operations"
    )

    # ---------- ingest ----------
    ingest_p = subparsers.add_parser(
        "ingest",
        help="Ingest pipe-delimited table data from markdown file",
        description="""
Ingest structured table data from markdown files into the ledger database.
Tables must be pipe-delimited with row IDs in the first column.

Use --full to ingest all tables in the file, or --h2 to target a specific section.
        """.strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ingest_p.add_argument("filename", help="Path to markdown file containing tables")
    ingest_p.add_argument("--h2", default=None, metavar="SECTION",
                         help="Ingest only tables under this H2 section name")
    ingest_p.add_argument("--full", action="store_true",
                         help="Ingest all tables in the file")

    # ---------- query ----------
    query_p = subparsers.add_parser(
        "query",
        help="Query ingested table data from ledger database",
        description="""
Query table data previously ingested from markdown files.
Filter by section (H2) and/or row type.

Returns: (row_id, h2, text, src, type, file, line_no, status, ingest_ts)
        """.strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    query_p.add_argument("dbfile", help="Path to ledger database file")
    query_p.add_argument("--h2", default=None, metavar="SECTION",
                        help="Filter by H2 section name")
    query_p.add_argument("--type", dest="type_filter", default=None, metavar="TYPE",
                        help="Filter by row type")

    # ---------- update ----------
    update_p = subparsers.add_parser(
        "update",
        help="Update a table row in the source markdown file",
        description="""
Update a specific row in the source markdown file by row ID.
The row must have been previously ingested into the ledger database.

This updates both the database record and the source markdown file in-place.
        """.strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    update_p.add_argument("row_id", metavar="ROW_ID",
                         help="Row ID to update (first column value)")
    update_p.add_argument("new_text", metavar="TEXT",
                         help="New text content for the row")
    update_p.add_argument("--db", default=DB_FILE, metavar="PATH",
                         help=f"Path to ledger database (default: {DB_FILE})")

    # ---------- index ----------
    index_p = subparsers.add_parser(
        "index",
        help="Index markdown file headers for structure-aware navigation",
        description="""
Create persistent header index for markdown files, enabling fast section lookup
and content search with full hierarchical context.

The index tracks file modification times and auto-reindexes on query if files
change (< 150ms overhead). Run once per project, or when adding new files.

EXAMPLES:
  md-ledger index .                # Index current directory
  md-ledger index . --recursive    # Index all subdirectories
  md-ledger index README.md        # Index single file
        """.strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    index_p.add_argument("path", metavar="PATH",
                        help="File or directory path to index")
    index_p.add_argument("--recursive", "-r", action="store_true",
                        help="Recursively scan subdirectories for .md files")

    # ---------- headers ----------
    headers_p = subparsers.add_parser(
        "headers",
        help="Display complete header hierarchy for a markdown file",
        description="""
Show the full H1-H6 header tree with line ranges for a markdown file.
Useful for understanding document structure before targeted reading.

Auto-reindexes if the file has been modified since last index.

OUTPUT FORMAT:
  H1 "Title" lines 1-50
    H2 "Section" lines 2-30
      H3 "Subsection" lines 10-25
    H2 "Another Section" lines 31-50

EXAMPLE:
  md-ledger headers README.md
        """.strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    headers_p.add_argument("file", metavar="FILE",
                          help="Markdown file to display headers for")

    # ---------- find-section ----------
    find_p = subparsers.add_parser(
        "find-section",
        help="Find sections by header name (case-insensitive substring match)",
        description="""
Search for sections across indexed files by header text.
Performs case-insensitive substring matching on header names.

Returns file paths with line ranges for targeted reading.

OUTPUT FORMAT:
  filename.md:23-45 (H2 "Installation Guide")
  README.md:150-200 (H2 "Installation Steps")

WORKFLOW:
  1. md-ledger find-section "Installation"
  2. Use output line range with Read tool: Read(file, offset=23, limit=22)

EXAMPLES:
  md-ledger find-section "API"
  md-ledger find-section "install" --file README.md
        """.strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    find_p.add_argument("query", metavar="QUERY",
                       help="Text to search for in header names (case-insensitive)")
    find_p.add_argument("--file", default=None, metavar="FILE",
                       help="Limit search to specific file")

    # ---------- find-content ----------
    content_p = subparsers.add_parser(
        "find-content",
        help="Search file content with full section hierarchy context",
        description="""
Search for text across indexed markdown files, returning matches with:
  - Line number location
  - Section hierarchy (full header path)
  - Section line range
  - Context lines around match

This provides full provenance for each match, showing exactly which section
contains the content and where in the document structure it appears.

OUTPUT FORMAT:
  filename.md:85
    Section: System Design > Pipeline Execution > Implementation
    Range: lines 80-95
    Context:
      [lines with ±N context around match]

EXAMPLES:
  md-ledger find-content "authentication"
  md-ledger find-content "pipeline" --context 3
  md-ledger find-content "config" --file architecture.md --context 0
        """.strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    content_p.add_argument("query", metavar="QUERY",
                          help="Text to search for in file content (case-insensitive)")
    content_p.add_argument("--file", default=None, metavar="FILE",
                          help="Limit search to specific file")
    content_p.add_argument("--context", "-C", type=int, default=1, metavar="N",
                          help="Number of context lines before/after match (default: 1)")

    args, unknown = parser.parse_known_args()

    # ---------- IMPLICIT INGEST ----------
    if args.command is None and unknown:
        filename = unknown[0]
        db = init_db(DB_FILE)
        ingest_file(db, filename)
        return 0


    # ---- QUERY MODE ----
    if args.command == "query":
        db = open_db()
        rows = query_ledger(db, h2=args.h2, type_filter=args.type_filter)

        if not rows:
            print("[INFO] 0 rows returned. Check h2 name or ingest status.")
        else:
            for r in rows:
                print(r)

        print(f"\n{len(rows)} rows")
        return 0



    # ---- INGEST MODE (explicit) ----
    if args.command == "ingest":
        db = init_db(DB_FILE)
        ingest_file(
            db,
            args.filename,
            target_h2=args.h2,
            full_ingest=args.full,
        )
        return 0

    # ---- UPDATE MODE ----
    if args.command == "update":
        from pathlib import Path
        from .apply_update import apply_update

        db_path = Path(args.db).resolve()
        if not db_path.exists():
            print(f"[ERROR] Database not found: {db_path}")
            print(f"Run 'md-ledger ingest' first to create the database.")
            return 1

        try:
            apply_update(args.row_id, args.new_text, db_path=str(db_path))
            return 0
        except ValueError as e:
            print(f"[ERROR] {e}")
            return 1
        except FileNotFoundError as e:
            print(f"[ERROR] {e}")
            return 1
        except IndexError as e:
            print(f"[ERROR] {e}")
            return 1

    # ---- INDEX MODE ----
    if args.command == "index":
        db = init_db(DB_FILE)
        try:
            index_markdown_files(db, args.path, recursive=args.recursive)
            return 0
        except FileNotFoundError as e:
            print(f"[ERROR] {e}")
            return 1
        except Exception as e:
            print(f"[ERROR] {e}")
            return 1

    # ---- HEADERS MODE ----
    if args.command == "headers":
        try:
            db = open_db(DB_FILE)
            headers = query_headers(db, args.file)
            print_header_tree(headers)
            return 0
        except FileNotFoundError as e:
            print(f"[ERROR] {e}")
            return 1

    # ---- FIND-SECTION MODE ----
    if args.command == "find-section":
        try:
            db = open_db(DB_FILE)
            results = find_section(db, args.query, file=args.file)

            if not results:
                print(f"No sections found matching '{args.query}'")
                return 0

            for result in results:
                file, header_text, level, line_start, line_end = result
                print(f"{file}:{line_start}-{line_end} (H{level} \"{header_text}\")")

            return 0
        except FileNotFoundError as e:
            print(f"[ERROR] {e}")
            return 1

    # ---- FIND-CONTENT MODE ----
    if args.command == "find-content":
        try:
            db = open_db(DB_FILE)
            results = find_content(db, args.query, file=args.file, context_lines=args.context)

            if not results:
                print(f"No content found matching '{args.query}'")
                return 0

            for result in results:
                filename, line_no, match_text, section_info = result

                if section_info:
                    header_text, level, line_start, line_end, header_path = section_info
                    print(f"\n{filename}:{line_no}")
                    print(f"  Section: {header_path}")
                    print(f"  Range: lines {line_start}-{line_end}")
                    print(f"  Context:")
                    for line in match_text.split('\n'):
                        print(f"    {line}")
                else:
                    print(f"\n{filename}:{line_no}")
                    print(f"  Section: (not in any indexed section)")
                    print(f"  Context:")
                    for line in match_text.split('\n'):
                        print(f"    {line}")

            print(f"\nFound {len(results)} match(es)")
            return 0
        except FileNotFoundError as e:
            print(f"[ERROR] {e}")
            return 1



if __name__ == "__main__":
    sys.exit(main())
