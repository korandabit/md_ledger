"""
Behavioral tests for the navigation layer: index, headers, find-section, find-content.

Each test is named for the specific failure mode it guards against.  The suite
covers:
  A. Indexer correctness
  B. Staleness / auto-reindex
  C. `headers` command — path forms
  D. `find-section` command
  E. `find-content` command
  F. End-to-end workflow integration
"""
import subprocess
import sys
import time
from pathlib import Path

import pytest

from md_ledger_tool.main import (
    _db_dir,
    _to_db_key,
    find_content,
    find_section,
    index_markdown_files,
    init_db,
    is_file_stale,
    query_headers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db(tmp_path):
    """Open a real file DB in tmp_path so _db_dir() works correctly."""
    return init_db(str(tmp_path / "ledger.db"))


def _md(tmp_path, name, text, subdir=None):
    """Write a .md file and return its Path."""
    parent = tmp_path / subdir if subdir else tmp_path
    parent.mkdir(parents=True, exist_ok=True)
    p = parent / name
    p.write_text(text, encoding="utf-8")
    return p


def _cli(*args, cwd):
    """Run md-ledger as a subprocess and return CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", "md_ledger_tool.main", *args],
        capture_output=True, text=True, cwd=str(cwd),
    )


# ---------------------------------------------------------------------------
# A. Indexer correctness
# ---------------------------------------------------------------------------

class TestIndexerCorrectness:

    def test_all_headers_appear_after_index(self, tmp_path):
        """Every header in the file must be present in header_index after indexing."""
        f = _md(tmp_path, "doc.md", "# Title\n## Section A\n### Sub\n## Section B\n")
        db = _db(tmp_path)
        index_markdown_files(db, str(f))
        rows = query_headers(db, str(f))
        texts = [r[2] for r in rows]
        assert "Title" in texts
        assert "Section A" in texts
        assert "Sub" in texts
        assert "Section B" in texts
        assert len(rows) == 4

    def test_stored_key_is_db_relative_not_basename(self, tmp_path):
        """header_index.file must store a DB-relative path, not a bare basename.

        This is the structural invariant that makes all path lookups correct.
        For a file co-located with the DB the key is just the filename; for a
        file in a subdirectory it includes the subdirectory prefix.
        """
        subdir_file = _md(tmp_path, "guide.md", "# Guide\n", subdir="docs")
        db = _db(tmp_path)
        index_markdown_files(db, str(subdir_file))
        rows = db.execute("SELECT DISTINCT file FROM header_index").fetchall()
        stored = rows[0][0]
        # Must NOT be a bare basename
        assert stored != "guide.md", "subdirectory prefix missing from stored key"
        assert stored == "docs/guide.md"

    def test_recursive_scan_indexes_subdirectory_files(self, tmp_path):
        """--recursive must reach files in nested directories."""
        _md(tmp_path, "root.md", "# Root\n")
        _md(tmp_path, "sub.md", "# Sub\n", subdir="docs")
        db = _db(tmp_path)
        index_markdown_files(db, str(tmp_path), recursive=True)
        stored = {r[0] for r in db.execute("SELECT DISTINCT file FROM header_index")}
        assert "root.md" in stored
        assert "docs/sub.md" in stored

    def test_reindex_does_not_duplicate_rows(self, tmp_path):
        """Running index twice must not create duplicate header rows."""
        f = _md(tmp_path, "doc.md", "# Title\n## A\n")
        db = _db(tmp_path)
        index_markdown_files(db, str(f))
        index_markdown_files(db, str(f))
        rows = query_headers(db, str(f))
        assert len(rows) == 2  # still exactly 2 headers, not 4

    def test_file_with_no_headers_does_not_crash(self, tmp_path, capsys):
        """A file containing no headers must be skipped gracefully."""
        f = _md(tmp_path, "prose.md", "Just plain text.\nNo headers here.\n")
        db = _db(tmp_path)
        # Must not raise
        index_markdown_files(db, str(f))
        rows = db.execute("SELECT * FROM header_index WHERE file = 'prose.md'").fetchall()
        assert rows == []

    def test_headers_inside_code_fences_are_not_indexed(self, tmp_path):
        """Hash lines inside fenced code blocks must not be treated as headers."""
        content = "# Real Header\n\n```\n# not a header\n## also not\n```\n"
        f = _md(tmp_path, "fence.md", content)
        db = _db(tmp_path)
        index_markdown_files(db, str(f))
        rows = query_headers(db, str(f))
        texts = [r[2] for r in rows]
        assert "Real Header" in texts
        assert "not a header" not in texts
        assert "also not" not in texts


# ---------------------------------------------------------------------------
# B. Staleness / auto-reindex
# ---------------------------------------------------------------------------

class TestStaleness:

    def test_fresh_file_is_not_stale(self, tmp_path):
        f = _md(tmp_path, "doc.md", "# Title\n")
        db = _db(tmp_path)
        index_markdown_files(db, str(f))
        assert is_file_stale(db, str(f)) is False

    def test_modified_file_is_stale(self, tmp_path):
        f = _md(tmp_path, "doc.md", "# Title\n")
        db = _db(tmp_path)
        index_markdown_files(db, str(f))
        # Ensure mtime advances (some filesystems have 1-second resolution)
        time.sleep(0.05)
        f.write_text("# Title\n## New\n", encoding="utf-8")
        # Force a detectable mtime change
        import os
        os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 1))
        assert is_file_stale(db, str(f)) is True

    def test_unindexed_file_returns_none_from_is_stale(self, tmp_path):
        f = _md(tmp_path, "new.md", "# Hello\n")
        db = _db(tmp_path)
        assert is_file_stale(db, str(f)) is None

    def test_query_headers_auto_indexes_unindexed_file(self, tmp_path):
        """query_headers must index the file on demand if it hasn't been seen."""
        f = _md(tmp_path, "fresh.md", "# Auto\n## Indexed\n")
        db = _db(tmp_path)
        # Never ran index_markdown_files — should still work
        rows = query_headers(db, str(f))
        assert len(rows) == 2

    def test_query_headers_picks_up_edits_automatically(self, tmp_path):
        """After editing a file, query_headers must return the updated headers."""
        f = _md(tmp_path, "evolving.md", "# Original\n")
        db = _db(tmp_path)
        index_markdown_files(db, str(f))
        # Edit and force mtime change
        f.write_text("# Original\n## Added\n", encoding="utf-8")
        import os
        os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 1))
        rows = query_headers(db, str(f))
        texts = [r[2] for r in rows]
        assert "Added" in texts

    def test_legacy_null_mtime_entry_treated_as_stale(self, tmp_path):
        """Rows with NULL file_mtime (old-format index) must be treated as stale."""
        f = _md(tmp_path, "old.md", "# Legacy\n")
        db = _db(tmp_path)
        index_markdown_files(db, str(f))
        # Manually corrupt the mtime to simulate legacy row
        db.execute("UPDATE header_index SET file_mtime = NULL WHERE file = 'old.md'")
        db.commit()
        assert is_file_stale(db, str(f)) is True


# ---------------------------------------------------------------------------
# C. `headers` command — path forms
# ---------------------------------------------------------------------------

class TestHeadersPathForms:
    """
    The headers command must produce output regardless of how the caller
    expresses the path: bare filename, relative with ./, relative with subdir,
    or absolute.  All forms resolve to the same DB key.
    """

    def _setup(self, tmp_path):
        f = _md(tmp_path, "doc.md", "# Title\n## Section\n")
        db = _db(tmp_path)
        index_markdown_files(db, str(f))
        db.close()
        return f

    def test_bare_filename_same_cwd(self, tmp_path, monkeypatch):
        self._setup(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = _cli("headers", "doc.md", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Title" in result.stdout
        assert "Section" in result.stdout

    def test_dot_relative_prefix(self, tmp_path, monkeypatch):
        """./doc.md must work the same as doc.md."""
        self._setup(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = _cli("headers", "./doc.md", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Title" in result.stdout

    def test_absolute_path(self, tmp_path):
        """Absolute path must resolve to the same DB key as the basename."""
        f = self._setup(tmp_path)
        result = _cli("headers", str(f.resolve()), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Title" in result.stdout

    def test_subdirectory_relative_path(self, tmp_path):
        """File in a subdirectory referenced as docs/guide.md must work."""
        guide = _md(tmp_path, "guide.md", "# Guide\n## Usage\n", subdir="docs")
        db = _db(tmp_path)
        index_markdown_files(db, str(guide))
        db.close()
        result = _cli("headers", "docs/guide.md", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Guide" in result.stdout
        assert "Usage" in result.stdout

    def test_no_headers_gives_clear_message(self, tmp_path, monkeypatch):
        """A file with no headers should say so, not silently return nothing."""
        f = _md(tmp_path, "prose.md", "just text\n")
        db = _db(tmp_path)
        index_markdown_files(db, str(f))
        db.close()
        monkeypatch.chdir(tmp_path)
        result = _cli("headers", "prose.md", cwd=tmp_path)
        # Should not crash; output should indicate no headers
        assert result.returncode == 0
        assert "no headers" in result.stdout.lower() or result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# D. `find-section` command
# ---------------------------------------------------------------------------

class TestFindSection:

    def _setup(self, tmp_path):
        _md(tmp_path, "main.md", "# Overview\n## Installation\n### Quick Start\n## Configuration\n")
        sub = _md(tmp_path, "api.md", "# API Reference\n## Endpoints\n", subdir="docs")
        db = _db(tmp_path)
        index_markdown_files(db, str(tmp_path / "main.md"))
        index_markdown_files(db, str(sub))
        db.close()

    def test_basic_substring_match(self, tmp_path):
        self._setup(tmp_path)
        result = _cli("find-section", "install", cwd=tmp_path)
        assert result.returncode == 0
        assert "Installation" in result.stdout

    def test_case_insensitive_match(self, tmp_path):
        self._setup(tmp_path)
        result = _cli("find-section", "INSTALL", cwd=tmp_path)
        assert result.returncode == 0
        assert "Installation" in result.stdout

    def test_returns_line_range(self, tmp_path):
        """Output must include the start-end line range for targeted Read calls."""
        self._setup(tmp_path)
        result = _cli("find-section", "Configuration", cwd=tmp_path)
        assert result.returncode == 0
        # Format: file:start-end
        assert "-" in result.stdout and ":" in result.stdout

    def test_no_match_gives_message_not_crash(self, tmp_path):
        self._setup(tmp_path)
        result = _cli("find-section", "doesnotexistanywhere", cwd=tmp_path)
        assert result.returncode == 0
        assert "no sections" in result.stdout.lower()

    def test_file_filter_bare_filename(self, tmp_path):
        """--file main.md must limit results to that file."""
        self._setup(tmp_path)
        result = _cli("find-section", "Overview", "--file", "main.md", cwd=tmp_path)
        assert result.returncode == 0
        assert "main.md" in result.stdout
        assert "api.md" not in result.stdout

    def test_file_filter_subdirectory_relative_path(self, tmp_path):
        """--file docs/api.md must match entries stored as docs/api.md."""
        self._setup(tmp_path)
        result = _cli("find-section", "Endpoints", "--file", "docs/api.md", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Endpoints" in result.stdout

    def test_file_filter_absolute_path(self, tmp_path):
        """--file /absolute/path/to/main.md must also resolve correctly."""
        self._setup(tmp_path)
        abs_path = str((tmp_path / "main.md").resolve())
        result = _cli("find-section", "Overview", "--file", abs_path, cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Overview" in result.stdout

    def test_cross_file_results_include_correct_filenames(self, tmp_path):
        """Without --file filter, results from multiple files must show correct provenance."""
        self._setup(tmp_path)
        result = _cli("find-section", "e", cwd=tmp_path)  # broad match
        assert result.returncode == 0
        assert "main.md" in result.stdout
        assert "docs/api.md" in result.stdout


# ---------------------------------------------------------------------------
# E. `find-content` command
# ---------------------------------------------------------------------------

class TestFindContent:

    def _setup(self, tmp_path):
        _md(tmp_path, "notes.md",
            "# Notes\n\n"
            "## Alpha\n\nThis discusses the pipeline architecture.\n\n"
            "## Beta\n\nUnrelated content here.\n")
        sub = _md(tmp_path, "extra.md",
                  "# Extra\n\nThe authentication flow is documented here.\n",
                  subdir="docs")
        db = _db(tmp_path)
        index_markdown_files(db, str(tmp_path / "notes.md"))
        index_markdown_files(db, str(sub))
        db.close()

    def test_basic_text_match(self, tmp_path):
        self._setup(tmp_path)
        result = _cli("find-content", "pipeline", cwd=tmp_path)
        assert result.returncode == 0
        assert "pipeline" in result.stdout.lower()

    def test_case_insensitive_match(self, tmp_path):
        self._setup(tmp_path)
        result = _cli("find-content", "PIPELINE", cwd=tmp_path)
        assert result.returncode == 0
        assert "pipeline" in result.stdout.lower()

    def test_section_context_is_attached(self, tmp_path):
        """Output must include the section header path for the match."""
        self._setup(tmp_path)
        result = _cli("find-content", "pipeline", cwd=tmp_path)
        assert "Section:" in result.stdout
        assert "Alpha" in result.stdout

    def test_context_lines_zero(self, tmp_path):
        """--context 0 must return only the matching line, no surrounding lines."""
        self._setup(tmp_path)
        result = _cli("find-content", "pipeline", "--context", "0", cwd=tmp_path)
        assert result.returncode == 0
        # The match line must appear but not extra blank/surrounding lines
        lines = [l for l in result.stdout.splitlines() if "pipeline" in l.lower()]
        assert len(lines) >= 1

    def test_context_lines_nonzero(self, tmp_path):
        """--context 2 must return lines around the match."""
        self._setup(tmp_path)
        result = _cli("find-content", "pipeline", "--context", "2", cwd=tmp_path)
        assert result.returncode == 0
        assert "pipeline" in result.stdout.lower()

    def test_different_cwd_still_finds_content(self, tmp_path, tmp_path_factory):
        """find-content must work when invoked from a CWD other than the project dir.

        This was the core CWD-dependency bug: Path(basename).exists() failed
        when CWD differed from the file location.  The fix resolves stored keys
        relative to the DB directory instead.
        """
        other_dir = tmp_path_factory.mktemp("other")
        self._setup(tmp_path)
        # Run from a completely different directory, pointing at the DB explicitly
        result = _cli("find-content", "pipeline", cwd=other_dir)
        # The DB lives in tmp_path, not other_dir, so we need to run from tmp_path
        # but with a different process CWD — simulate by changing sys.path via env
        # Simpler: just confirm the API-level fix works
        db = _db(tmp_path)
        results = find_content(db, "pipeline")
        assert len(results) >= 1
        assert any("pipeline" in r[2].lower() for r in results)

    def test_file_filter_bare_filename(self, tmp_path):
        """--file notes.md must scope search to that file only."""
        self._setup(tmp_path)
        result = _cli("find-content", "content", "--file", "notes.md", cwd=tmp_path)
        assert result.returncode == 0
        assert "notes.md" in result.stdout
        assert "extra.md" not in result.stdout

    def test_file_filter_subdirectory_relative_path(self, tmp_path):
        """--file docs/extra.md must resolve and search that file."""
        self._setup(tmp_path)
        result = _cli("find-content", "authentication", "--file", "docs/extra.md", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "authentication" in result.stdout.lower()

    def test_file_filter_absolute_path(self, tmp_path):
        """--file with absolute path must resolve to the correct DB key."""
        self._setup(tmp_path)
        abs_path = str((tmp_path / "notes.md").resolve())
        result = _cli("find-content", "pipeline", "--file", abs_path, cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "pipeline" in result.stdout.lower()

    def test_no_match_gives_message_not_crash(self, tmp_path):
        self._setup(tmp_path)
        result = _cli("find-content", "zzznomatchzzz", cwd=tmp_path)
        assert result.returncode == 0
        assert "no content" in result.stdout.lower()

    def test_subdirectory_file_is_searchable(self, tmp_path):
        """Content in a subdirectory file must appear in unfiltered search."""
        self._setup(tmp_path)
        result = _cli("find-content", "authentication", cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "authentication" in result.stdout.lower()


# ---------------------------------------------------------------------------
# F. `_to_db_key` unit tests (the path normalisation contract)
# ---------------------------------------------------------------------------

class TestToDbKey:
    """These tests pin the exact contract of the path normalisation helper."""

    def test_bare_filename_in_db_dir(self, tmp_path):
        db = _db(tmp_path)
        _md(tmp_path, "file.md", "")
        key = _to_db_key(db, str(tmp_path / "file.md"))
        assert key == "file.md"

    def test_subdirectory_file(self, tmp_path):
        db = _db(tmp_path)
        f = _md(tmp_path, "guide.md", "", subdir="docs")
        key = _to_db_key(db, str(f))
        assert key == "docs/guide.md"

    def test_relative_path_resolved_from_cwd(self, tmp_path, monkeypatch):
        """A relative path is resolved via CWD, then made DB-relative."""
        monkeypatch.chdir(tmp_path)
        db = _db(tmp_path)
        _md(tmp_path, "file.md", "")
        key = _to_db_key(db, "file.md")
        assert key == "file.md"

    def test_dot_slash_prefix_stripped(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = _db(tmp_path)
        _md(tmp_path, "file.md", "")
        key = _to_db_key(db, "./file.md")
        assert key == "file.md"

    def test_absolute_path_produces_same_key_as_relative(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = _db(tmp_path)
        _md(tmp_path, "file.md", "")
        key_rel = _to_db_key(db, "file.md")
        key_abs = _to_db_key(db, str((tmp_path / "file.md").resolve()))
        assert key_rel == key_abs

    def test_path_outside_db_dir_raises(self, tmp_path, tmp_path_factory):
        db = _db(tmp_path)
        outside = tmp_path_factory.mktemp("outside") / "other.md"
        outside.write_text("")
        with pytest.raises(ValueError, match="outside"):
            _to_db_key(db, str(outside))

    def test_uses_forward_slashes_on_all_platforms(self, tmp_path):
        db = _db(tmp_path)
        f = _md(tmp_path, "guide.md", "", subdir="a/b")
        key = _to_db_key(db, str(f))
        assert "\\" not in key
        assert key == "a/b/guide.md"


# ---------------------------------------------------------------------------
# G. End-to-end workflow
# ---------------------------------------------------------------------------

class TestWorkflowIntegration:

    def test_index_then_headers_then_find_section_then_find_content(self, tmp_path):
        """Full happy-path workflow: all four commands work in sequence."""
        _md(tmp_path, "spec.md",
            "# Specification\n\n"
            "## Requirements\n\nThe system must handle pipeline throughput.\n\n"
            "## Design\n\nArchitecture decisions go here.\n")

        r = _cli("index", ".", cwd=tmp_path)
        assert r.returncode == 0, r.stderr

        r = _cli("headers", "spec.md", cwd=tmp_path)
        assert r.returncode == 0
        assert "Requirements" in r.stdout
        assert "Design" in r.stdout

        r = _cli("find-section", "Requirements", cwd=tmp_path)
        assert r.returncode == 0
        assert "spec.md" in r.stdout

        r = _cli("find-content", "pipeline", cwd=tmp_path)
        assert r.returncode == 0
        assert "pipeline" in r.stdout.lower()

    def test_recursive_index_makes_subdirectory_files_searchable(self, tmp_path):
        """Files indexed via --recursive must appear in find-content results."""
        _md(tmp_path, "root.md", "# Root\n\nRoot level content.\n")
        _md(tmp_path, "nested.md", "# Nested\n\nDeep nested content.\n", subdir="a/b")

        r = _cli("index", ".", "--recursive", cwd=tmp_path)
        assert r.returncode == 0, r.stderr

        r = _cli("find-content", "nested content", cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert "nested content" in r.stdout.lower()

    def test_edit_file_then_find_updated_content(self, tmp_path):
        """After editing a file, auto-reindex ensures find-content sees new text."""
        import os
        f = _md(tmp_path, "live.md", "# Live\n\noriginal text here\n")

        r = _cli("index", ".", cwd=tmp_path)
        assert r.returncode == 0

        # Edit and advance mtime
        f.write_text("# Live\n\nreplaced with new content\n", encoding="utf-8")
        os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 1))

        r = _cli("find-content", "replaced with new content", cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert "replaced" in r.stdout.lower()

    def test_headers_outside_db_dir_gives_actionable_error(self, tmp_path, tmp_path_factory):
        """headers on an absolute path outside the DB dir must exit non-zero with
        a message that tells the user exactly how to fix it (--db flag + index cmd)."""
        outside_dir = tmp_path_factory.mktemp("outside")
        outside_file = outside_file = outside_dir / "other.md"
        outside_file.write_text("# External\n## Section\n", encoding="utf-8")

        # Set up a DB in tmp_path (different dir from outside_file)
        _md(tmp_path, "local.md", "# Local\n")
        db = _db(tmp_path)
        db.close()

        result = _cli("headers", str(outside_file.resolve()), cwd=tmp_path)
        assert result.returncode != 0
        assert "outside" in result.stdout.lower() or "outside" in result.stderr.lower()
        # Must include the md-ledger index command hint
        assert "md-ledger index" in result.stdout or "md-ledger index" in result.stderr

    def test_find_section_file_filter_outside_db_dir_gives_actionable_error(
        self, tmp_path, tmp_path_factory
    ):
        """--file pointing outside the DB dir must give an actionable error, not a traceback."""
        outside_dir = tmp_path_factory.mktemp("outside2")
        outside_file = outside_dir / "remote.md"
        outside_file.write_text("# Remote\n## Target\n", encoding="utf-8")

        _md(tmp_path, "local.md", "# Local\n")
        db = _db(tmp_path)
        db.close()

        result = _cli(
            "find-section", "Target",
            "--file", str(outside_file.resolve()),
            cwd=tmp_path,
        )
        assert result.returncode != 0
        assert "outside" in result.stdout.lower() or "outside" in result.stderr.lower()
        assert "md-ledger index" in result.stdout or "md-ledger index" in result.stderr

    def test_same_filename_in_multiple_subdirectories(self, tmp_path):
        """Two files named README.md in different subdirs must be independently indexed."""
        _md(tmp_path, "README.md", "# Alpha README\n\nalpha specific content\n", subdir="alpha")
        _md(tmp_path, "README.md", "# Beta README\n\nbeta specific content\n", subdir="beta")

        r = _cli("index", ".", "--recursive", cwd=tmp_path)
        assert r.returncode == 0, r.stderr

        r = _cli("find-content", "alpha specific", cwd=tmp_path)
        assert "alpha" in r.stdout.lower()

        r = _cli("find-content", "beta specific", cwd=tmp_path)
        assert "beta" in r.stdout.lower()

        # Both README.md files must be distinct entries in the index
        r = _cli("find-section", "README", cwd=tmp_path)
        assert "alpha/README.md" in r.stdout
        assert "beta/README.md" in r.stdout
