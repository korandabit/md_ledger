import subprocess
import pathlib
from md_ledger_tool.main import init_db, ingest_file


def test_update_cli_success(tmp_path, monkeypatch):
    """Test successful update via CLI"""
    md = tmp_path / "md"
    md.mkdir()

    # Create test markdown file
    test_md = md / "test.md"
    test_md.write_text("""## constraints
C001 | original text | src1 | definition
C002 | another row | src2 | hypothesis
""")

    monkeypatch.chdir(tmp_path)

    # Ingest the file
    db = init_db("ledger.db")
    ingest_file(db, "test.md", full_ingest=True)
    db.close()

    # Run update via CLI
    result = subprocess.run(
        ["python", "-m", "md_ledger_tool.main", "update", "C001", "updated text"],
        capture_output=True,
        text=True,
        cwd=tmp_path
    )

    assert result.returncode == 0
    assert "Updated row C001" in result.stdout

    # Verify the file was updated
    updated_content = test_md.read_text()
    assert "updated text" in updated_content
    assert "original text" not in updated_content


def test_update_cli_row_not_found(tmp_path, monkeypatch):
    """Test update with non-existent row_id"""
    md = tmp_path / "md"
    md.mkdir()

    test_md = md / "test.md"
    test_md.write_text("""## constraints
C001 | text | src1 | definition
""")

    monkeypatch.chdir(tmp_path)

    db = init_db("ledger.db")
    ingest_file(db, "test.md", full_ingest=True)
    db.close()

    # Try to update non-existent row
    result = subprocess.run(
        ["python", "-m", "md_ledger_tool.main", "update", "C999", "new text"],
        capture_output=True,
        text=True,
        cwd=tmp_path
    )

    assert result.returncode == 1
    assert "not found" in result.stdout


def test_update_cli_db_not_found(tmp_path, monkeypatch):
    """Test update when database doesn't exist"""
    monkeypatch.chdir(tmp_path)

    result = subprocess.run(
        ["python", "-m", "md_ledger_tool.main", "update", "C001", "text"],
        capture_output=True,
        text=True,
        cwd=tmp_path
    )

    assert result.returncode == 1
    assert "Database not found" in result.stdout


def test_update_cli_custom_db_path(tmp_path, monkeypatch):
    """Test update with custom database path"""
    md = tmp_path / "md"
    md.mkdir()

    test_md = md / "test.md"
    test_md.write_text("""## constraints
C001 | original | src1 | definition
""")

    monkeypatch.chdir(tmp_path)

    custom_db = "custom.db"
    db = init_db(custom_db)
    ingest_file(db, "test.md", full_ingest=True)
    db.close()

    # Update using custom DB path
    result = subprocess.run(
        ["python", "-m", "md_ledger_tool.main", "update", "C001", "new text", "--db", custom_db],
        capture_output=True,
        text=True,
        cwd=tmp_path
    )

    assert result.returncode == 0
    assert "Updated row C001" in result.stdout

    updated_content = test_md.read_text()
    assert "new text" in updated_content
