import sqlite3
from pathlib import Path
import hashlib
from datetime import datetime
import argparse
import sys

DB_FILE = "ledger.db"

def open_db(db_path=None):
    path = Path(db_path or DB_FILE).resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"No ledger.db in current directory ({path.parent}). Run ingest first."
        )
    print(f"[md-ledger] using DB: {path}")
    return sqlite3.connect(path)


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
    ingest_ts = datetime.utcnow().isoformat()
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


def main():
    # implicit ingest: md-ledger somefile.md
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        filename = sys.argv[1]
        db = init_db(DB_FILE)
        ingest_file(db, filename)
        return 0

    # if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        # db = sqlite3.connect(DB_FILE)
        # ingest_file(db, sys.argv[1])
        # return 0

    parser = argparse.ArgumentParser(prog="md-ledger")

    subparsers = parser.add_subparsers(dest="command", required=False)

    # ---------- ingest ----------
    ingest_p = subparsers.add_parser("ingest", help="Ingest a markdown file")
    ingest_p.add_argument("filename")
    ingest_p.add_argument("--h2", default=None)
    ingest_p.add_argument("--full", action="store_true")

    # ---------- query ----------
    query_p = subparsers.add_parser("query", help="Query the ledger DB")
    query_p.add_argument("dbfile")
    query_p.add_argument("--h2", default=None)
    query_p.add_argument("--type", dest="type_filter", default=None)

    # ---------- update ----------
    update_p = subparsers.add_parser("update", help="Update a row in the source Markdown file")
    update_p.add_argument("row_id", help="Row ID to update")
    update_p.add_argument("new_text", help="New text content for the row")
    update_p.add_argument("--db", default=DB_FILE, help="Path to ledger DB (default: ledger.db)")

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



if __name__ == "__main__":
    sys.exit(main())
