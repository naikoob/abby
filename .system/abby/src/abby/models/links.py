"""Data models for vault link graphs, backlinks, broken audits, and refactoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


@dataclass
class NoteLinkRecord:
    """Represents an individual link reference extracted from a source note."""

    source_path: str
    target_title: str
    target_heading: Optional[str] = None
    target_alias: Optional[str] = None
    link_syntax: Literal["wikilink", "markdown"] = "wikilink"
    is_embed: bool = False
    line_number: int = 1
    resolved_path: Optional[str] = None
    candidate_paths: list[str] = field(default_factory=list)
    is_ambiguous: bool = False
    depth: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize link record to dictionary."""
        return {
            "source_path": self.source_path,
            "target_title": self.target_title,
            "target_heading": self.target_heading,
            "target_alias": self.target_alias,
            "link_syntax": self.link_syntax,
            "is_embed": self.is_embed,
            "line_number": self.line_number,
            "resolved_path": self.resolved_path,
            "is_ambiguous": self.is_ambiguous,
            "candidate_paths": list(self.candidate_paths),
            "depth": self.depth,
        }


@dataclass
class BacklinkOccurrence:
    """Represents a single incoming reference occurrence."""

    source_path: str
    line_number: int
    alias: Optional[str] = None
    heading: Optional[str] = None
    link_syntax: Literal["wikilink", "markdown"] = "wikilink"
    is_embed: bool = False
    depth: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize occurrence to dictionary."""
        return {
            "source_path": self.source_path,
            "line_number": self.line_number,
            "alias": self.alias,
            "heading": self.heading,
            "link_syntax": self.link_syntax,
            "is_embed": self.is_embed,
            "depth": self.depth,
        }


@dataclass
class BacklinkSummary:
    """Represents aggregate incoming references to a note."""

    target_note: str
    target_title: str
    backlinks: list[BacklinkOccurrence] = field(default_factory=list)

    @property
    def total_backlinks(self) -> int:
        """Return total count of incoming references."""
        return len(self.backlinks)

    def to_dict(self) -> dict[str, Any]:
        """Serialize backlink summary to dictionary."""
        return {
            "target_note": self.target_note,
            "target_title": self.target_title,
            "total_backlinks": self.total_backlinks,
            "backlinks": [b.to_dict() for b in self.backlinks],
        }


@dataclass
class BrokenLinkItem:
    """Represents an unresolved reference detected during broken link audit."""

    source_path: str
    line_number: int
    target: str
    heading: Optional[str] = None
    link_syntax: Literal["wikilink", "markdown"] = "wikilink"
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize broken link item to dictionary."""
        return {
            "source_path": self.source_path,
            "line_number": self.line_number,
            "target": self.target,
            "heading": self.heading,
            "link_syntax": self.link_syntax,
            "raw_text": self.raw_text,
        }


@dataclass
class RefactorFileModification:
    """Represents a modified referencing note during refactoring."""

    path: str
    occurrences_replaced: int
    lines_modified: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize file modification to dictionary."""
        return {
            "path": self.path,
            "occurrences_replaced": self.occurrences_replaced,
            "lines_modified": list(self.lines_modified),
        }


@dataclass
class RefactorResult:
    """Represents the complete result of a link refactoring operation."""

    old_title: str
    new_title: str
    file_renamed: Optional[str] = None
    files_modified: list[RefactorFileModification] = field(default_factory=list)
    total_occurrences: int = 0
    is_dry_run: bool = False
    source_file: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize refactor result to dictionary."""
        return {
            "old_title": self.old_title,
            "new_title": self.new_title,
            "file_renamed": self.file_renamed,
            "total_occurrences": self.total_occurrences,
            "is_dry_run": self.is_dry_run,
            "files_modified": [f.to_dict() for f in self.files_modified],
        }


@dataclass
class OrphanReport:
    """Represents isolated and unreferenced notes across the vault."""

    orphans: list[str] = field(default_factory=list)
    unreferenced: list[str] = field(default_factory=list)
    domain_filter: Optional[str] = None
    included_inbox: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize orphan report to dictionary."""
        return {
            "domain_filter": self.domain_filter,
            "included_inbox": self.included_inbox,
            "total_orphans": len(self.orphans),
            "orphans": list(self.orphans),
            "total_unreferenced": len(self.unreferenced),
            "unreferenced": list(self.unreferenced),
        }
