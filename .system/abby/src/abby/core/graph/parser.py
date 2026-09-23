"""Link syntax extraction and code block masking utilities for Abby Knowledge Vault.

Pure text-processing utilities with zero dependencies on SQLite cache or refactor engines.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

from abby.constants import (
    FENCED_CODE_BLOCK_PATTERN,
    INLINE_CODE_PATTERN,
    MARKDOWN_LINK_PATTERN,
    WIKILINK_PATTERN,
)
from abby.models.links import NoteLinkRecord

__all__ = [
    "extract_links_from_text",
    "strip_code_blocks",
]


def strip_code_blocks(text: str) -> str:
    """Mask fenced code blocks and inline code backticks while preserving exact newlines.

    Replaces non-newline characters inside code blocks with spaces so that line numbers
    of subsequent text remain 100% identical to the original source document.
    """

    def _mask(match: re.Match[str]) -> str:
        s = match.group(0)
        return "".join("\n" if c == "\n" else " " for c in s)

    # First mask multi-line fenced code blocks
    masked = re.sub(FENCED_CODE_BLOCK_PATTERN, _mask, text)
    # Then mask single-line inline code backticks
    masked = re.sub(INLINE_CODE_PATTERN, _mask, masked)
    return masked


def extract_links_from_text(text: str, source_path: str = "") -> list[NoteLinkRecord]:
    """Parse all functional Wikilinks and local relative Markdown links from note content.

    Ignores syntax inside code blocks and ignores external web URLs (http/https/mailto).
    Preserves 1-indexed line numbers.
    """
    raw_records: list[tuple[int, NoteLinkRecord]] = []
    masked = strip_code_blocks(text)

    # 1. Parse Obsidian Wikilinks: !?[[Target(#Heading)?(|Alias)?]]
    for m in re.finditer(WIKILINK_PATTERN, masked):
        is_embed = bool(m.group(1))
        raw_target = m.group(2).strip()
        heading = m.group(3).strip() if m.group(3) else None
        alias = m.group(4).strip() if m.group(4) else None

        if not raw_target:
            continue

        # Calculate exact 1-indexed line number
        line_num = text[: m.start()].count("\n") + 1

        # Normalize target title: strip .md if explicitly included
        target_title = raw_target
        if target_title.lower().endswith(".md"):
            target_title = target_title[:-3]

        raw_records.append(
            (
                m.start(),
                NoteLinkRecord(
                    source_path=source_path,
                    target_title=target_title,
                    target_heading=heading,
                    target_alias=alias,
                    link_syntax="wikilink",
                    is_embed=is_embed,
                    line_number=line_num,
                ),
            )
        )

    # 2. Parse Local Markdown Links: !?[Label](path ("title")?)
    for m in re.finditer(MARKDOWN_LINK_PATTERN, masked):
        is_embed = bool(m.group(1))
        label = m.group(2).strip()
        raw_url = m.group(3).strip()

        if not raw_url:
            continue

        # Skip external web protocols and in-document section anchors
        url_lower = raw_url.lower()
        if url_lower.startswith(
            ("http://", "https://", "mailto:", "ftp://", "data:")
        ) or raw_url.startswith("#"):
            continue

        # Calculate exact 1-indexed line number
        line_num = text[: m.start()].count("\n") + 1

        # Decode URL-encoded characters (e.g. %20 -> space)
        decoded_url = unquote(raw_url)

        # Separate target path and optional anchor
        heading = None
        if "#" in decoded_url:
            target_file_part, heading_part = decoded_url.split("#", 1)
            target_path_part = target_file_part.strip()
            heading = heading_part.strip() or None
        else:
            target_path_part = decoded_url

        if not target_path_part:
            continue

        raw_records.append(
            (
                m.start(),
                NoteLinkRecord(
                    source_path=source_path,
                    target_title=target_path_part,
                    target_heading=heading,
                    target_alias=label if label else None,
                    link_syntax="markdown",
                    is_embed=is_embed,
                    line_number=line_num,
                ),
            )
        )

    # Sort links by exact occurrence in source file
    raw_records.sort(key=lambda item: item[0])
    return [r for _, r in raw_records]

