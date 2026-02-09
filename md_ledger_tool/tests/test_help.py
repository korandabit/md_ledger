"""
Tests for CLI help functionality.

Verifies that --help works for main command and all subcommands,
and that help text includes expected content.
"""
import subprocess
import sys


def test_main_help():
    """Test main --help command."""
    result = subprocess.run(
        [sys.executable, "-m", "md_ledger_tool.main", "--help"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "Token-efficient, structure-aware Markdown" in result.stdout
    assert "EXAMPLES:" in result.stdout
    assert "TOKEN EFFICIENCY:" in result.stdout
    assert "WORKFLOW:" in result.stdout

    # Check all commands are listed
    commands = ["ingest", "query", "update", "index", "headers", "find-section", "find-content"]
    for cmd in commands:
        assert cmd in result.stdout


def test_index_help():
    """Test index --help command."""
    result = subprocess.run(
        [sys.executable, "-m", "md_ledger_tool.main", "index", "--help"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "Create persistent header index" in result.stdout
    assert "EXAMPLES:" in result.stdout
    assert "--recursive" in result.stdout
    assert "auto-reindexes" in result.stdout


def test_headers_help():
    """Test headers --help command."""
    result = subprocess.run(
        [sys.executable, "-m", "md_ledger_tool.main", "headers", "--help"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "header tree" in result.stdout
    assert "OUTPUT FORMAT:" in result.stdout
    assert "EXAMPLE:" in result.stdout


def test_find_section_help():
    """Test find-section --help command."""
    result = subprocess.run(
        [sys.executable, "-m", "md_ledger_tool.main", "find-section", "--help"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "case-insensitive substring match" in result.stdout
    assert "OUTPUT FORMAT:" in result.stdout
    assert "WORKFLOW:" in result.stdout
    assert "EXAMPLES:" in result.stdout


def test_find_content_help():
    """Test find-content --help command."""
    result = subprocess.run(
        [sys.executable, "-m", "md_ledger_tool.main", "find-content", "--help"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "Section hierarchy" in result.stdout
    assert "OUTPUT FORMAT:" in result.stdout
    assert "EXAMPLES:" in result.stdout
    assert "--context" in result.stdout


def test_ingest_help():
    """Test ingest --help command."""
    result = subprocess.run(
        [sys.executable, "-m", "md_ledger_tool.main", "ingest", "--help"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "pipe-delimited" in result.stdout
    assert "--full" in result.stdout
    assert "--h2" in result.stdout


def test_update_help():
    """Test update --help command."""
    result = subprocess.run(
        [sys.executable, "-m", "md_ledger_tool.main", "update", "--help"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "Update a specific row" in result.stdout
    assert "ROW_ID" in result.stdout
    assert "--db" in result.stdout


def test_query_help():
    """Test query --help command."""
    result = subprocess.run(
        [sys.executable, "-m", "md_ledger_tool.main", "query", "--help"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "Query table data" in result.stdout
    assert "--h2" in result.stdout
    assert "--type" in result.stdout
