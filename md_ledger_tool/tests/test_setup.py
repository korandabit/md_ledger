"""
Tests for:
  - `md-ledger setup` command: idempotent hook registration
  - `md-ledger query --h2` CLI: case-insensitive match regression (fix: aba9553)
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _cli(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "md_ledger_tool.main", *args],
        capture_output=True, text=True, cwd=str(cwd),
    )


def _md(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# setup command
# ---------------------------------------------------------------------------

class TestSetupCommand:

    def test_setup_installs_hook_script(self, tmp_path):
        """setup must copy md_ledger_guard.py into the target hooks dir."""
        hooks_dir = tmp_path / "hooks"
        settings_path = tmp_path / "settings.json"

        result = subprocess.run(
            [
                sys.executable, "-c",
                (
                    "from md_ledger_tool.main import _setup_claude_integration; "
                    f"_setup_claude_integration("
                    f"    hooks_dir=r'{hooks_dir}', "
                    f"    settings_path=r'{settings_path}'"
                    f")"
                ),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert (hooks_dir / "md_ledger_guard.py").exists()

    def test_setup_registers_hook_in_settings(self, tmp_path):
        """setup must write a PreToolUse entry that references md_ledger_guard."""
        hooks_dir = tmp_path / "hooks"
        settings_path = tmp_path / "settings.json"

        from md_ledger_tool.main import _setup_claude_integration
        _setup_claude_integration(hooks_dir=hooks_dir, settings_path=settings_path)

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        pre = settings.get("hooks", {}).get("PreToolUse", [])
        commands = [
            cmd_entry.get("command", "")
            for block in pre
            for cmd_entry in block.get("hooks", [])
        ]
        assert any("md_ledger_guard" in c for c in commands)

    def test_setup_is_idempotent(self, tmp_path):
        """Running setup twice must not duplicate the hook registration."""
        hooks_dir = tmp_path / "hooks"
        settings_path = tmp_path / "settings.json"

        from md_ledger_tool.main import _setup_claude_integration
        _setup_claude_integration(hooks_dir=hooks_dir, settings_path=settings_path)
        _setup_claude_integration(hooks_dir=hooks_dir, settings_path=settings_path)

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        pre = settings.get("hooks", {}).get("PreToolUse", [])
        guard_entries = [
            b for b in pre
            if any("md_ledger_guard" in e.get("command", "") for e in b.get("hooks", []))
        ]
        assert len(guard_entries) == 1, "Hook registered more than once after two setup calls"

    def test_setup_preserves_existing_settings(self, tmp_path):
        """setup must not clobber existing settings.json content."""
        hooks_dir = tmp_path / "hooks"
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps({"permissions": {"allow": ["Bash(*)"]}}, indent=2),
            encoding="utf-8",
        )

        from md_ledger_tool.main import _setup_claude_integration
        _setup_claude_integration(hooks_dir=hooks_dir, settings_path=settings_path)

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        # Original key must still be there
        assert settings.get("permissions", {}).get("allow") == ["Bash(*)"]
        # And the hook must have been added
        assert "hooks" in settings


# ---------------------------------------------------------------------------
# query --h2 CLI (regression for aba9553: case mismatch)
# ---------------------------------------------------------------------------

class TestQueryH2CLI:

    def _ingest_setup(self, tmp_path, monkeypatch):
        """Create a minimal markdown with pipe-delimited rows and ingest it."""
        monkeypatch.chdir(tmp_path)
        # ingest expects pipe-delimited rows (no leading/trailing pipes, no header row)
        _md(tmp_path, "data.md", (
            "# Data\n\n"
            "## Constraints\n\n"
            "C1 | first constraint | src1 | definition\n"
            "C2 | second constraint | src2 | hypothesis\n"
        ))
        r = _cli("ingest", "data.md", "--h2", "Constraints", cwd=tmp_path)
        assert r.returncode == 0, r.stderr

    def test_query_h2_exact_match(self, tmp_path, monkeypatch):
        self._ingest_setup(tmp_path, monkeypatch)
        r = _cli("query", "ledger.db", "--h2", "constraints", cwd=tmp_path)
        assert r.returncode == 0
        assert "C1" in r.stdout
        assert "C2" in r.stdout

    def test_query_h2_case_insensitive(self, tmp_path, monkeypatch):
        """--h2 match must be case-insensitive (regression: aba9553)."""
        self._ingest_setup(tmp_path, monkeypatch)
        r = _cli("query", "ledger.db", "--h2", "CONSTRAINTS", cwd=tmp_path)
        assert r.returncode == 0
        assert "C1" in r.stdout

    def test_query_h2_no_match_gives_info_message(self, tmp_path, monkeypatch):
        """--h2 with no matching rows must print an info message, not crash."""
        self._ingest_setup(tmp_path, monkeypatch)
        r = _cli("query", "ledger.db", "--h2", "nonexistent", cwd=tmp_path)
        assert r.returncode == 0
        assert "0 rows" in r.stdout or "info" in r.stdout.lower()
