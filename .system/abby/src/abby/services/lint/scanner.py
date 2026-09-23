"""Lexical frontmatter scanner and tokenizer integration for OKF linting."""

from __future__ import annotations

from abby.models.okf import ParsedFrontmatter
from abby.services.okf_parser import tokenize_frontmatter

__all__ = [
    "ParsedFrontmatter",
    "scan_frontmatter",
    "tokenize_frontmatter",
]


def scan_frontmatter(content: str) -> ParsedFrontmatter:
    """Scan and tokenize note frontmatter for schema evaluation and remediation.

    Args:
        content: Raw markdown text of note.

    Returns:
        ParsedFrontmatter with extracted metadata, line numbers, and body.
    """
    return tokenize_frontmatter(content)
