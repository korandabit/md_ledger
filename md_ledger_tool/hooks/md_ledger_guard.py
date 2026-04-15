#!/usr/bin/env python3
"""
PreToolUse hook: enforce md-ledger workflow and config-driven verb blocking.

Reads ~/.claude/verb_config.json to build four verb sets at startup:

    deny_md    - block when verb targets a .md file argument
    deny       - block always, regardless of arguments
    warn_md    - inject advisory context when verb targets a .md file argument
    warn       - inject advisory context always

Falls back to hardcoded defaults if verb_config.json is absent.

The md-ledger Read guard (large .md without offset/limit) is always active
regardless of config — it enforces the navigation workflow, not verb blocking.

Exit 0 in all cases; allow/deny/warn expressed via JSON output.
"""

import json
import re
import sys
from pathlib import Path

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------

VERB_CONFIG_PATH = Path.home() / '.claude' / 'verb_config.json'

# Files shorter than this threshold are fine to Read whole.
MD_LINE_THRESHOLD = 50

# Shell operators that separate command segments.
_SHELL_SPLIT = re.compile(r'[;&|]+')

# Hardcoded fallback verb sets used when config is absent.
_FALLBACK_DENY_MD  = {'cat', 'head', 'tail', 'sed', 'grep', 'rg'}
_FALLBACK_WARN_MD  = {'awk', 'find'}
_FALLBACK_DENY     = set()
_FALLBACK_WARN     = {'cd'}


def _load_verb_sets() -> tuple[set, set, set, set]:
    """
    Read verb_config.json and return (deny_md, deny, warn_md, warn) sets.
    Falls back to hardcoded defaults on missing or malformed config.
    """
    try:
        if VERB_CONFIG_PATH.exists():
            config = json.loads(VERB_CONFIG_PATH.read_text(encoding='utf-8'))
            verbs = config.get('verbs', {})
            deny_md = {v for v, c in verbs.items() if c.get('action') == 'deny_md'}
            deny    = {v for v, c in verbs.items() if c.get('action') == 'deny'}
            warn_md = {v for v, c in verbs.items() if c.get('action') == 'warn_md'}
            warn    = {v for v, c in verbs.items() if c.get('action') == 'warn'}
            return deny_md, deny, warn_md, warn
    except (json.JSONDecodeError, OSError):
        pass
    return _FALLBACK_DENY_MD, _FALLBACK_DENY, _FALLBACK_WARN_MD, _FALLBACK_WARN


def _alternative_for(verb: str) -> str | None:
    """Look up the configured alternative description for a verb."""
    try:
        if VERB_CONFIG_PATH.exists():
            config = json.loads(VERB_CONFIG_PATH.read_text(encoding='utf-8'))
            return config.get('verbs', {}).get(verb, {}).get('alternative')
    except (json.JSONDecodeError, OSError):
        pass
    return None


# Load once at import time (hook process is short-lived per call).
DENY_MD, DENY_ALWAYS, WARN_MD, WARN_ALWAYS = _load_verb_sets()

# ------------------------------------------------------------------
# JSON response helpers
# ------------------------------------------------------------------

def _deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def _warn(context: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "additionalContext": context,
        }
    }))
    sys.exit(0)


def _allow() -> None:
    sys.exit(0)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _count_lines(path: str) -> int | None:
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return sum(1 for _ in fh)
    except OSError:
        return None


def _fmt(path: str) -> str:
    return path.replace('\\', '/')


def _parse_segments(cmd: str) -> list[tuple[str, list[str]]]:
    """
    Split a shell command into (verb, args) per segment.

    Operates on command words so verbs appearing inside quoted string
    arguments (e.g. echo '...cat README.md...') are not flagged.
    """
    segments = []
    for segment in _SHELL_SPLIT.split(cmd):
        words = segment.strip().split()
        if not words:
            continue
        verb = Path(words[0]).name.lower()
        segments.append((verb, words[1:]))
    return segments


def _md_arg(args: list[str]) -> str | None:
    """Return the first argument that looks like a .md filepath, or None."""
    return next(
        (a for a in args if re.search(r'\.md\b', a, re.IGNORECASE)),
        None,
    )


# ------------------------------------------------------------------
# Read guard — always active
# ------------------------------------------------------------------

def check_read(tool_input: dict) -> None:
    """Block un-navigated reads of large .md files."""
    path = tool_input.get('file_path', '')
    if not path.lower().endswith('.md'):
        return

    # Targeted reads (offset or limit supplied) are allowed — navigation happened.
    if tool_input.get('offset') is not None or tool_input.get('limit') is not None:
        return

    fp = _fmt(path)
    _deny(
        f"[md-ledger guard] Read({Path(path).name}) blocked. Navigate first:\n"
        f"\n"
        f"  md-ledger headers {fp}\n"
        f"      -> header tree with line ranges\n"
        f"\n"
        f"  md-ledger find-section \"section name\"\n"
        f"      -> file:start-end for any header\n"
        f"\n"
        f"  md-ledger find-content \"search text\"\n"
        f"      -> cross-file content search\n"
        f"\n"
        f"Then: Read({fp}, offset=<start>, limit=<lines>)"
    )


# ------------------------------------------------------------------
# Bash guard — config-driven
# ------------------------------------------------------------------

def check_bash(tool_input: dict) -> None:
    """
    Block or warn on Bash commands based on verb_config.json classifications.

    Checks each command segment independently to avoid false positives from
    verbs appearing inside quoted string arguments.
    """
    cmd = tool_input.get('command', '')
    segments = _parse_segments(cmd)

    for verb, args in segments:
        alt = _alternative_for(verb)
        alt_desc = f'use {alt} instead' if alt else 'see verb_config.json for alternative'

        # --- deny always (no file arg required) ---
        if verb in DENY_ALWAYS:
            _deny(
                f"[md-ledger guard] Bash({verb} ...) blocked — {alt_desc}.\n"
                f"Classified as 'deny' in ~/.claude/verb_config.json."
            )

        # --- deny on .md argument ---
        if verb in DENY_MD:
            target = _md_arg(args)
            if target:
                fp = _fmt(target)
                filename = Path(fp).name
                _deny(
                    f"[md-ledger guard] Bash({verb} ...{filename}) blocked — {alt_desc}.\n"
                    f"\n"
                    f"  md-ledger headers {fp}\n"
                    f"      -> header tree with line ranges\n"
                    f"\n"
                    f"  md-ledger find-section \"section name\"\n"
                    f"      -> locate section, get line range\n"
                    f"\n"
                    f"  Read({fp}, offset=<start>, limit=<lines>)\n"
                    f"      -> read just that section\n"
                    f"\n"
                    f"For search: md-ledger find-content \"text\" or Grep tool."
                )

        # --- warn always ---
        if verb in WARN_ALWAYS:
            _warn(
                f"[md-ledger guard] Bash({verb} ...) advisory: {alt_desc}. "
                f"Proceeding, but prefer the alternative when possible."
            )

        # --- warn on .md argument ---
        if verb in WARN_MD:
            target = _md_arg(args)
            if target:
                fp = _fmt(target)
                _warn(
                    f"[md-ledger guard] Bash({verb} ...{Path(fp).name}) advisory: {alt_desc}. "
                    f"Proceeding — consider md-ledger or dedicated tool if this is navigation."
                )


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        # Malformed / empty stdin — nothing to guard against.
        _allow()

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})

    if tool_name == 'Read':
        check_read(tool_input)
    elif tool_name == 'Bash':
        check_bash(tool_input)

    _allow()


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Guard crashed — never block tool access due to guard bugs.
        sys.exit(0)
