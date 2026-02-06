
import pathlib
from main import ingest_all, query, init_db

def test_malformed_rows_ignored(tmp_path, monkeypatch):
    md = tmp_path / "md"
    md.mkdir()
    (md / "bad.md").write_text("""
## constraints
BAD ROW WITHOUT DELIMITERS
C3 | ok | src | definition
""")

    monkeypatch.chdir(tmp_path)
    init_db()
    ingest_all()

    rows = query("constraints", "definition")
    assert len(rows) == 1
    assert rows[0][0] == "C3"
