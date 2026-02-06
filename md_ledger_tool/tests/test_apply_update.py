
import pathlib, sqlite3
from main import ingest_all, init_db
from apply_update import apply_update

def test_apply_update_changes_only_target_line(tmp_path, monkeypatch):
    md = tmp_path / "md"
    md.mkdir()
    f = md / "t.md"
    f.write_text("""
## constraints
C9 | old text | src | definition
""")

    monkeypatch.chdir(tmp_path)
    init_db()
    ingest_all()

    apply_update("C9", "new text")

    out = f.read_text()
    assert "new text" in out
    assert "old text" not in out
