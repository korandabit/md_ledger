
import sqlite3, pathlib, shutil
from main import ingest_all, query, init_db

def setup_tmp(tmp_path):
    md = tmp_path / "md"
    md.mkdir()
    (md / "t.md").write_text("""
## constraints
C1 | a | src1 | definition
C2 | b | src2 | hypothesis

## other
X1 | nope | x | definition
""")
    return md

def test_ingest_and_query(tmp_path, monkeypatch):
    md = setup_tmp(tmp_path)
    monkeypatch.chdir(tmp_path)

    init_db()
    ingest_all()

    rows = query("constraints", "definition")
    assert len(rows) == 1
    assert rows[0][0] == "C1"
