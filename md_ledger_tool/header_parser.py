"""
Header parsing module for Markdown files.

Extracts H1-H6 headers with line numbers and calculates section boundaries.
"""

from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path


@dataclass
class HeaderNode:
    """Raw header from markdown file."""
    text: str
    level: int  # 1-6 for H1-H6
    line_no: int  # 1-indexed line number


@dataclass
class HeaderSection:
    """Header with calculated boundaries and hierarchy."""
    text: str
    level: int
    line_start: int  # Section content starts here (1-indexed)
    line_end: int  # Section ends here (inclusive, 1-indexed)
    parent_id: Optional[int] = None  # ID of parent section


def parse_headers(file_path: str) -> List[HeaderNode]:
    """
    Parse markdown file and extract all headers (H1-H6) with line numbers.

    Args:
        file_path: Path to markdown file

    Returns:
        List of HeaderNode objects with text, level, and line number
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    lines = path.read_text(encoding='utf-8').splitlines()
    headers = []
    in_code_fence = False

    for idx, line in enumerate(lines):
        line_strip = line.strip()

        # Track code fence state to skip headers in code blocks
        if line_strip.startswith("```"):
            in_code_fence = not in_code_fence
            continue

        # Skip if in code fence
        if in_code_fence:
            continue

        # Detect ATX-style headers (# Header)
        if line_strip.startswith("#"):
            # Count leading #
            level = 0
            for char in line_strip:
                if char == "#":
                    level += 1
                else:
                    break

            # Valid header levels are 1-6
            if 1 <= level <= 6:
                # Extract header text (strip leading # and whitespace)
                text = line_strip[level:].strip()
                if text:  # Only add if there's actual text
                    headers.append(HeaderNode(
                        text=text,
                        level=level,
                        line_no=idx + 1  # Convert to 1-indexed
                    ))

    return headers


def calculate_boundaries(headers: List[HeaderNode], total_lines: int) -> List[HeaderSection]:
    """
    Calculate line_end for each header section.

    Rules:
    - Section content starts on the line after the header
    - Section ends where the next same-or-higher level header starts
    - Last section ends at EOF

    Args:
        headers: List of HeaderNode from parse_headers
        total_lines: Total lines in the file

    Returns:
        List of HeaderSection with boundaries calculated
    """
    if not headers:
        return []

    sections = []

    for i, header in enumerate(headers):
        line_start = header.line_no + 1  # Content starts after header line

        # Find where this section ends
        line_end = total_lines  # Default to EOF

        # Look for next header at same or higher level
        for next_header in headers[i + 1:]:
            if next_header.level <= header.level:
                # Section ends just before the next same-or-higher level header
                line_end = next_header.line_no - 1
                break

        sections.append(HeaderSection(
            text=header.text,
            level=header.level,
            line_start=line_start,
            line_end=line_end
        ))

    return sections


def build_hierarchy(sections: List[HeaderSection]) -> List[HeaderSection]:
    """
    Assign parent_id based on nesting level.

    H3 under H2 gets parent_id pointing to that H2's index in the list.
    Parent is the most recent header with level < current level.

    Args:
        sections: List of HeaderSection from calculate_boundaries

    Returns:
        Same list with parent_id populated
    """
    # Track most recent header at each level
    level_stack = {}  # {level: section_index}

    for i, section in enumerate(sections):
        # Find parent: most recent header with level < current level
        parent_idx = None
        for level in range(section.level - 1, 0, -1):
            if level in level_stack:
                parent_idx = level_stack[level]
                break

        section.parent_id = parent_idx
        level_stack[section.level] = i

    return sections


def parse_file_headers(file_path: str) -> List[HeaderSection]:
    """
    Convenience function: parse headers and calculate full structure in one call.

    Args:
        file_path: Path to markdown file

    Returns:
        List of HeaderSection with boundaries and hierarchy
    """
    headers = parse_headers(file_path)
    total_lines = len(Path(file_path).read_text(encoding='utf-8').splitlines())
    sections = calculate_boundaries(headers, total_lines)
    sections = build_hierarchy(sections)
    return sections
