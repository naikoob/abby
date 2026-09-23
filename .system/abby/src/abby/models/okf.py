"""Open Knowledge Format (OKF) data models, lifecycle result types, and re-exported serialization helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import sys
from typing import Any, Optional

from abby.models.trust import (
    GenerationRecord,
    ProvenanceSource,
    TrustTier,
    VerificationEvent,
    VerifyResult,
    evaluate_staleness,
    resolve_trust_tier,
)
from abby.utils.time import now_iso
from abby.utils.yaml import format_yaml_tag, unescape_yaml_string


@dataclass
class ParsedFrontmatter:
    """Tokenized representation of a Markdown document's frontmatter."""

    has_frontmatter: bool
    is_closed: bool
    raw_frontmatter: str
    body_content: str
    fields: dict[str, tuple[str, int]]  # key -> (raw_value, 1-indexed line_number)
    tags: list[tuple[str, int]]  # list of (unescaped_tag, 1-indexed line_number)
    tags_line: int  # 1-indexed line number where 'tags:' was declared
    tags_is_scalar: bool  # True if tags were formatted as scalar/comma string
    closing_line_number: int  # 1-indexed line number of closing delimiter
    generated: Optional[dict[str, str]] = None
    verified: list[dict[str, str]] = field(default_factory=list)
    stale_after: Optional[str] = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    sources_is_malformed: bool = False



def _sanitize_yaml_value(val: str) -> str:
    """Sanitize string for YAML double-quoted value."""
    return (
        val.replace("\r", "")
        .replace("\n", " ")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )


def _format_generated_block(generated: dict[str, str]) -> list[str]:
    lines = ["generated:"]
    gen_by = generated.get("by", "")
    lines.append(f"  by: {gen_by}")
    gen_at = generated.get("at")
    if gen_at:
        lines.append(f'  at: "{gen_at}"')
    return lines


def _format_verified_block(verified: list[dict[str, str]]) -> list[str]:
    lines = ["verified:"]
    for v in verified:
        v_by = v.get("by", "")
        v_at = v.get("at")
        if v_at:
            lines.append(f'  - by: {v_by}\n    at: "{v_at}"')
        else:
            lines.append(f"  - by: {v_by}")
    return lines


def _format_sources_block(sources: list[dict[str, Any]]) -> list[str]:
    lines = ["sources:"]
    for s in sources:
        res = s.get("resource", "")
        lines.append(f'  - resource: "{res}"')
        if "id" in s and s["id"]:
            lines.append(f"    id: {s['id']}")
        if "title" in s and s["title"]:
            lines.append(f'    title: "{s["title"]}"')
        if "author" in s and s["author"]:
            lines.append(f'    author: "{s["author"]}"')
        if "usage_count" in s and s["usage_count"] is not None:
            lines.append(f"    usage_count: {s['usage_count']}")
        if "last_modified" in s and s["last_modified"]:
            lines.append(f'    last_modified: "{s["last_modified"]}"')
    return lines


@dataclass
class OKFFrontmatter:
    """Represents the Open Knowledge Format metadata header written at the top of markdown documents."""

    title: str
    description: Optional[str] = None
    created: str = field(default_factory=now_iso)
    updated: Optional[str] = None
    type: str = "inbox"
    status: str = "unprocessed"
    tags: list[str] = field(default_factory=lambda: ["inbox"])

    # OKF v0.2 Additions
    generated: Optional[dict[str, str]] = None
    verified: list[dict[str, str]] = field(default_factory=list)
    stale_after: Optional[str] = None
    sources: list[dict[str, Any]] = field(default_factory=list)

    @property
    def trust_tier(self) -> str:
        """Dynamically compute OKF v0.2 trust tier from verified records."""
        return resolve_trust_tier(self.verified)

    @property
    def is_stale(self) -> bool:
        """Dynamically compute whether the note has passed its stale_after instant."""
        return evaluate_staleness(self.stale_after)

    def to_yaml(self) -> str:
        """Serialize frontmatter into standard YAML block fenced by triple dashes."""
        raw_title = self.title or "Untitled Note"
        lines = ["---", f'title: "{_sanitize_yaml_value(raw_title)}"']

        if self.description:
            lines.append(f'description: "{_sanitize_yaml_value(self.description)}"')

        created_str = self.created or ""
        lines.append(f'created: "{created_str}"')

        if self.updated:
            lines.append(f'updated: "{_sanitize_yaml_value(self.updated)}"')

        lines.append(f"type: {self.type or 'inbox'}")
        lines.append(f"status: {self.status or 'unprocessed'}")

        if self.tags:
            lines.append("tags:")
            for tag in self.tags:
                lines.append(format_yaml_tag(tag))
        else:
            lines.append("tags: []")

        if self.stale_after:
            lines.append(f'stale_after: "{_sanitize_yaml_value(self.stale_after)}"')

        if self.generated:
            lines.extend(_format_generated_block(self.generated))

        if self.verified:
            lines.extend(_format_verified_block(self.verified))

        if self.sources:
            lines.extend(_format_sources_block(self.sources))

        lines.append("---")
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_markdown(
        cls, markdown: str, default_title: str = "Untitled Note"
    ) -> OKFFrontmatter:
        """Parse frontmatter from markdown content using abby.services.okf_parser."""
        raise NotImplementedError(
            "Use abby.services.okf_parser.parse_okf_frontmatter to parse markdown."
        )


@dataclass
class InboxNote:
    """Represents a created note artifact within 00 - Inbox/."""

    title: str
    filename: str
    relative_path: str
    absolute_path: Path
    frontmatter: OKFFrontmatter
    body: str = ""

    def to_markdown(self) -> str:
        """Render complete markdown file content with frontmatter and body."""
        fm = self.frontmatter.to_yaml()
        body_content = self.body.strip()
        if body_content:
            return f"{fm}\n{body_content}\n"
        return f"{fm}\n"


@dataclass
class DirectoryStatus:
    """Represents the audit status of a required vault directory."""

    name: str
    expected_relative_path: str
    exists: bool
    is_dir: bool
    item_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "exists": self.exists,
            "is_dir": self.is_dir,
            "item_count": self.item_count,
        }


@dataclass
class VaultHealthReport:
    """Represents the complete evaluation produced by abby check and abby info."""

    vault_root: str
    healthy: bool
    directories: dict[str, DirectoryStatus]
    missing_directories: list[str]
    system_status: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "vault_root": self.vault_root,
            "directories": {
                name: status.to_dict() for name, status in self.directories.items()
            },
            "missing_directories": self.missing_directories,
            "system_status": self.system_status,
        }


@dataclass
class TriageNoteItem:
    """Represents an individual note listed within a domain queue."""

    filename: str
    path: str
    title: str
    created: str
    age_days: int
    status: str
    updated: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.updated is None:
            del data["updated"]
        return data


@dataclass
class MoveResult:
    """Represents the outcome of a note relocation and frontmatter update."""

    success: bool
    source_path: str
    target_path: str
    title: str
    previous_status: str
    new_status: str
    timestamp: str = field(default_factory=now_iso)
    is_dry_run: bool = False
    description: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source_path
        d["target"] = self.target_path
        return d


@dataclass
class ArchiveResult:
    """Represents the outcome of archiving a note."""

    success: bool
    source_path: str
    target_path: str
    title: str
    archived_at: str = field(default_factory=now_iso)
    is_dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "ArchiveResult",
    "DirectoryStatus",
    "GenerationRecord",
    "InboxNote",
    "MoveResult",
    "OKFFrontmatter",
    "ParsedFrontmatter",
    "ProvenanceSource",
    "TriageNoteItem",
    "TrustTier",
    "VaultHealthReport",
    "VerificationEvent",
    "VerifyResult",
    "evaluate_staleness",
    "resolve_trust_tier",
]

