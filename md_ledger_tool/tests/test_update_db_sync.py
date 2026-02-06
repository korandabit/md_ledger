import sqlite3
from md_ledger_tool.main import init_db, ingest_file
from md_ledger_tool.apply_update import apply_update


def test_update_syncs_db_and_file(tmp_path, monkeypatch):
    """Test that update modifies both markdown file and database"""
    md = tmp_path / "md"
    md.mkdir()

    test_md = md / "test.md"
    test_md.write_text("""## constraints
C001 | original text | src1 | definition
""")

    monkeypatch.chdir(tmp_path)

    # Ingest and verify initial state
    db = init_db("ledger.db")
    ingest_file(db, "test.md", full_ingest=True)

    cursor = db.execute("SELECT text, status FROM ledger WHERE row_id='C001'")
    row = cursor.fetchone()
    assert row[0] == "original text"
    assert row[1] == "clean"
    db.close()

    # Update via apply_update
    apply_update("C001", "updated text", db_path="ledger.db")

    # Verify file was updated
    content = test_md.read_text()
    assert "updated text" in content
    assert "original text" not in content

    # Verify database was updated
    db = sqlite3.connect("ledger.db")
    cursor = db.execute("SELECT text, status FROM ledger WHERE row_id='C001'")
    row = cursor.fetchone()
    assert row[0] == "updated text", "DB text should be updated"
    assert row[1] == "updated", "DB status should be 'updated'"
    db.close()


def test_update_timestamp_changes(tmp_path, monkeypatch):
    """Test that ingest_ts is updated on manual update"""
    md = tmp_path / "md"
    md.mkdir()

    test_md = md / "test.md"
    test_md.write_text("""## constraints
C001 | original | src1 | definition
""")

    monkeypatch.chdir(tmp_path)

    # Ingest
    db = init_db("ledger.db")
    ingest_file(db, "test.md", full_ingest=True)

    cursor = db.execute("SELECT ingest_ts FROM ledger WHERE row_id='C001'")
    original_ts = cursor.fetchone()[0]
    db.close()

    # Wait and update
    import time
    time.sleep(0.01)  # Ensure timestamp differs

    apply_update("C001", "new text", db_path="ledger.db")

    # Verify timestamp changed
    db = sqlite3.connect("ledger.db")
    cursor = db.execute("SELECT ingest_ts FROM ledger WHERE row_id='C001'")
    new_ts = cursor.fetchone()[0]
    db.close()

    assert new_ts != original_ts, "Timestamp should be updated"
    assert new_ts > original_ts, "New timestamp should be more recent"
