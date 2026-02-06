import sqlite3
import pathlib

DB_PATH = "ledger.db"
MD_DIR = "md"


def apply_update(row_id: str, new_text: str, db_path: str = None):
    """
    Update a single row in the Markdown file by row_id.

    Only the 'text' column (2nd column) is replaced.
    Fails fast if row/file/line is missing or malformed.

    Args:
        row_id: The row ID to update
        new_text: New text content for the row
        db_path: Path to ledger DB (default: ledger.db)
    """
    db = sqlite3.connect(db_path or DB_PATH)
    row = db.execute(
        "SELECT file, line_no FROM ledger WHERE row_id=?",
        (row_id,),
    ).fetchone()

    if not row:
        db.close()
        raise ValueError(f"Row {row_id} not found in ledger.")

    file_name, line_no = row
    path = pathlib.Path(MD_DIR) / file_name
    if not path.exists():
        db.close()
        raise FileNotFoundError(f"Markdown file '{file_name}' not found in {MD_DIR}")

    lines = path.read_text().splitlines()

    if line_no > len(lines) or line_no < 1:
        db.close()
        raise IndexError(f"Line number {line_no} out of bounds in {file_name} (valid: 1-{len(lines)})")

    # Parse the line (convert 1-indexed line_no to 0-indexed)
    line = lines[line_no - 1].strip()
    parts = [p.strip() for p in line.split("|")]

    if len(parts) != 4:
        db.close()
        raise ValueError(f"Malformed row at {file_name}:{line_no+1} -> '{line}'")

    # Replace only the 'text' column
    parts[1] = f" {new_text} "
    lines[line_no - 1] = " | ".join(parts)

    # Write back to markdown file
    path.write_text("\n".join(lines))

    # Update database to match
    from datetime import datetime
    update_ts = datetime.utcnow().isoformat()

    db.execute(
        "UPDATE ledger SET text=?, ingest_ts=?, status=? WHERE row_id=?",
        (new_text, update_ts, 'updated', row_id)
    )
    db.commit()
    db.close()

    print(f"Updated row {row_id} in {file_name} at line {line_no+1}")
