"""
Tests for two confirmed bugs fixed in this project:

Bug 2: `query --h2` returned 0 rows after successful ingest because the
       query subcommand called open_db() ignoring args.dbfile entirely.

Bug 3: `update` path resolution was hardcoded to a `md/` subdirectory.
       Source files co-located with the db (the common case) were not found.
"""
import subprocess
import pathlib
from md_ledger_tool.main import init_db, ingest_file
from md_ledger_tool.apply_update import apply_update


# ---------------------------------------------------------------------------
# Bug 2: query --h2 returns 0 rows even after successful ingest
# ---------------------------------------------------------------------------

def test_query_h2_returns_rows_after_ingest(tmp_path, monkeypatch):
    """query --h2 must return ingested rows from the named section."""
    md = tmp_path / "md"
    md.mkdir()
    (md / "data.md").write_text(
        "## Dependencies\n"
        "D001 | first dep | src1 | link\n"
        "D002 | second dep | src2 | link\n"
    )
    monkeypatch.chdir(tmp_path)

    db = init_db("ledger.db")
    ingest_file(db, "data.md", full_ingest=True)
    db.close()

    result = subprocess.run(
        ["python", "-m", "md_ledger_tool.main", "query", "ledger.db", "--h2", "Dependencies"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "D001" in result.stdout
    assert "D002" in result.stdout
    assert "2 rows" in result.stdout


def test_query_h2_case_insensitive(tmp_path, monkeypatch):
    """h2 matching is lowercased on ingest; query must pass the value through."""
    md = tmp_path / "md"
    md.mkdir()
    (md / "data.md").write_text(
        "## Constraints\n"
        "C001 | text | src | definition\n"
    )
    monkeypatch.chdir(tmp_path)

    db = init_db("ledger.db")
    ingest_file(db, "data.md", full_ingest=True)
    db.close()

    # ingest lowercases h2; query should match regardless of caller's casing
    result = subprocess.run(
        ["python", "-m", "md_ledger_tool.main", "query", "ledger.db", "--h2", "constraints"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "C001" in result.stdout
    assert "1 rows" in result.stdout


def test_query_no_h2_filter_returns_all(tmp_path, monkeypatch):
    """query without --h2 should return every ingested row."""
    md = tmp_path / "md"
    md.mkdir()
    (md / "data.md").write_text(
        "## Alpha\n"
        "A001 | a | s | t\n"
        "## Beta\n"
        "B001 | b | s | t\n"
    )
    monkeypatch.chdir(tmp_path)

    db = init_db("ledger.db")
    ingest_file(db, "data.md", full_ingest=True)
    db.close()

    result = subprocess.run(
        ["python", "-m", "md_ledger_tool.main", "query", "ledger.db"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "A001" in result.stdout
    assert "B001" in result.stdout
    assert "2 rows" in result.stdout


# ---------------------------------------------------------------------------
# Bug 3: update path resolution hardcoded to md/ subdirectory
# ---------------------------------------------------------------------------

def test_update_resolves_file_colocated_with_db(tmp_path, monkeypatch):
    """update must find the source file when it lives next to the db, not in md/."""
    # Source file directly in tmp_path — NO md/ subdir
    source = tmp_path / "notes.md"
    source.write_text(
        "## section\n"
        "N001 | original | src | type\n"
    )
    monkeypatch.chdir(tmp_path)

    db = init_db("ledger.db")
    ingest_file(db, str(source), full_ingest=True)
    db.close()

    apply_update("N001", "updated text", db_path=str(tmp_path / "ledger.db"))

    content = source.read_text()
    assert "updated text" in content
    assert "original" not in content


def test_update_resolves_file_via_db_path_arg(tmp_path, monkeypatch):
    """update with explicit --db path must resolve source relative to that db."""
    subdir = tmp_path / "store"
    subdir.mkdir()
    source = subdir / "ledger_source.md"
    source.write_text(
        "## items\n"
        "I001 | old value | s | t\n"
    )

    db_path = subdir / "custom.db"
    db = init_db(str(db_path))
    ingest_file(db, str(source), full_ingest=True)
    db.close()

    monkeypatch.chdir(tmp_path)  # CWD is NOT where the db or file lives

    result = subprocess.run(
        ["python", "-m", "md_ledger_tool.main",
         "update", "I001", "new value", "--db", str(db_path)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Updated row I001" in result.stdout
    assert "new value" in source.read_text()


def test_update_legacy_md_subdir_still_works(tmp_path, monkeypatch):
    """Backward compat: update still works when source file is in a md/ subdir."""
    md = tmp_path / "md"
    md.mkdir()
    source = md / "legacy.md"
    source.write_text(
        "## section\n"
        "L001 | old | src | type\n"
    )
    monkeypatch.chdir(tmp_path)

    db = init_db("ledger.db")
    ingest_file(db, str(source), full_ingest=True)
    db.close()

    apply_update("L001", "new", db_path=str(tmp_path / "ledger.db"))

    assert "new" in source.read_text()
    assert "old" not in source.read_text()


def test_update_missing_file_gives_clear_error(tmp_path, monkeypatch):
    """update raises FileNotFoundError with a useful message when file is gone."""
    md = tmp_path / "md"
    md.mkdir()
    source = md / "gone.md"
    source.write_text(
        "## section\n"
        "G001 | text | src | type\n"
    )
    monkeypatch.chdir(tmp_path)

    db = init_db("ledger.db")
    ingest_file(db, str(source), full_ingest=True)
    db.close()

    source.unlink()  # delete the file after ingest

    result = subprocess.run(
        ["python", "-m", "md_ledger_tool.main", "update", "G001", "new text"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 1
    assert "not found" in result.stdout.lower()
