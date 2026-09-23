"""Centralized domain authority, taxonomy mapping, and path canonicalization for Abby Knowledge Vault."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from abby.constants import (
    DOMAIN_ALIAS_MAP,
    DOMAIN_DEFAULT_STATUS,
    DOMAIN_DEFAULT_TYPE,
    KNOWLEDGE_DIRECTORIES,
    VALID_NOTE_DOMAINS,
)


EXTRA_ALIASES: dict[str, str] = {
    "project": "01 - Projects",
    "area": "02 - Areas",
    "resource": "03 - Resources",
    "archive": "04 - Archives",
    "asset": "05 - Assets",
    "assets": "05 - Assets",
}


def canonicalize_domain(domain_str: Optional[str]) -> Optional[str]:
    """Map domain alias or folder name to its canonical directory name (e.g. 'projects' -> '01 - Projects')."""
    if not domain_str:
        return None
    cleaned = domain_str.strip()
    if cleaned in VALID_NOTE_DOMAINS or cleaned in KNOWLEDGE_DIRECTORIES:
        return cleaned
    cleaned_lower = cleaned.lower()
    if cleaned_lower in DOMAIN_ALIAS_MAP:
        return DOMAIN_ALIAS_MAP[cleaned_lower]
    return EXTRA_ALIASES.get(cleaned_lower)


def resolve_domain_name(domain_key: str) -> str:
    """Resolve domain key or alias to canonical name, raising ValueError if invalid."""
    canonical = canonicalize_domain(domain_key)
    if not canonical:
        raise ValueError(
            f"Invalid domain '{domain_key}'. Must be one of: "
            + ", ".join(DOMAIN_ALIAS_MAP.keys())
        )
    return canonical


def is_valid_domain(name: str) -> bool:
    """Return True if the given string represents a valid canonical domain or recognized alias."""
    return canonicalize_domain(name) is not None


def resolve_domain_from_path(rel_path: str | Path) -> Optional[str]:
    """Extract and canonicalize the top-level domain from a note path (handling both POSIX and Windows separators)."""
    if not rel_path:
        return None
    path_str = str(rel_path).replace("\\", "/").strip("/")
    parts = path_str.split("/")
    if not parts or not parts[0]:
        return None
    first = parts[0]
    return canonicalize_domain(first)


def get_domain_defaults(domain: str) -> tuple[str, str]:
    """Return (default_status, default_type) for a domain."""
    canonical = canonicalize_domain(domain) or domain
    status = DOMAIN_DEFAULT_STATUS.get(canonical, "active")
    type_ = DOMAIN_DEFAULT_TYPE.get(canonical, "project-note")
    return status, type_
