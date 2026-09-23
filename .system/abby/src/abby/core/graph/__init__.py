"""Knowledge graph analysis, parsing, diagnostics, caching, and refactoring subsystem."""

from __future__ import annotations

from typing import Any

from abby.core.graph.cache import (
    resolve_cached_links,
    update_active_backlinks,
)
from abby.core.graph.diagnostics import (
    find_orphan_notes,
    find_unreferenced_notes,
    format_backlinks_text,
    format_broken_links_text,
    format_outbound_links_text,
    get_ambiguous_candidates,
    resolve_note_target,
    scan_broken_links,
)
from abby.core.graph.parser import (
    extract_links_from_text,
    strip_code_blocks,
)
from abby.core.graph.refactor import (
    refactor_note,
    rewrite_note_links,
)
from abby.core.graph.traversal import (
    query_backlinks,
    query_outbound_links,
)

__all__ = [
    "extract_links_from_text",
    "find_orphan_notes",
    "find_unreferenced_notes",
    "format_backlinks_text",
    "format_broken_links_text",
    "format_outbound_links_text",
    "get_ambiguous_candidates",
    "query_backlinks",
    "query_outbound_links",
    "refactor_note",
    "resolve_cached_links",
    "resolve_note_target",
    "rewrite_note_links",
    "scan_broken_links",
    "strip_code_blocks",
    "update_active_backlinks",
]

