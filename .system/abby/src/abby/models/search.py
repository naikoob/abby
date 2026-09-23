"""Search data models for Abby Knowledge Vault."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SearchFilter:
    """Encapsulates search parameters parsed from CLI arguments."""

    query: Optional[str] = None
    scope: str = "all"  # "all", "title", "content"
    domain: Optional[str] = None
    status: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    tag_conjunction: str = "AND"  # "AND" or "OR"
    type: Optional[str] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None
    updated_after: Optional[str] = None
    updated_before: Optional[str] = None
    limit: Optional[int] = None
    json_mode: bool = False
    snippets: bool = False
    trust: Optional[str] = None
    fresh_only: bool = False
    stale_only: bool = False


@dataclass
class SearchMatchItem:
    """Represents an individual matching note in search results."""

    filename: str
    path: str
    title: str
    domain: str
    status: str
    type: str
    description: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    snippet: Optional[str] = None
    trust_tier: str = "unverified"
    is_stale: bool = False
    active_backlinks: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict matching NoteSearchResult note item schema."""
        return {
            "filename": self.filename,
            "path": self.path,
            "title": self.title,
            "domain": self.domain,
            "status": self.status,
            "type": self.type,
            "description": self.description,
            "created": self.created,
            "updated": self.updated,
            "tags": list(self.tags),
            "snippet": self.snippet,
            "trust_tier": self.trust_tier,
            "is_stale": self.is_stale,
            "active_backlinks": self.active_backlinks,
        }


@dataclass
class SearchResultPayload:
    """Represents the complete search response adhering to the JSON contract."""

    query: Optional[str]
    domain: Optional[str]
    status: Optional[str]
    tags: list[str]
    count: int
    total_matches: int
    notes: list[SearchMatchItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload into dictionary conforming to JSON schema contract."""
        return {
            "query": self.query,
            "domain": self.domain,
            "status": self.status,
            "tags": list(self.tags),
            "count": self.count,
            "total_matches": self.total_matches,
            "notes": [item.to_dict() for item in self.notes],
        }
