"""Tool schema definitions for Abby Model Context Protocol (MCP) server."""

from __future__ import annotations

from typing import Any

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "vault_check": {
        "name": "vault_check",
        "description": "Perform a read-only audit of vault directory structure and verify standard PARA+ domains.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "vault_init": {
        "name": "vault_init",
        "description": "Idempotently scaffold any missing standard PARA+ directories in the vault.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "note_capture": {
        "name": "note_capture",
        "description": "Capture a new note into 00 - Inbox/ with title, optional body, description, tags, and canonical OKF frontmatter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Natural title of the new note (e.g. 'Project Alpha Kickoff')",
                },
                "body": {
                    "type": "string",
                    "description": "Optional Markdown body content",
                },
                "description": {
                    "type": "string",
                    "description": "Optional 1-2 sentence executive summary (TL;DR) of the note's intent",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags to include in frontmatter (without '#' prefixes)",
                },
                "generated": {
                    "type": "object",
                    "properties": {
                        "by": {"type": "string"},
                        "at": {"type": "string"},
                    },
                    "description": "Optional creation provenance mapping",
                },
                "verified": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "by": {"type": "string"},
                            "at": {"type": "string"},
                        },
                        "required": ["by"],
                    },
                    "description": "Optional initial verification attestations",
                },
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "resource": {"type": "string"},
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "author": {"type": "string"},
                        },
                        "required": ["resource"],
                    },
                    "description": "Optional attributed upstream sources",
                },
            },
            "required": ["title"],
        },
    },
    "note_read": {
        "name": "note_read",
        "description": "Retrieve the complete Markdown content, frontmatter metadata, and raw text of a note in the vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "Relative path, natural title, or filename of the note to read (e.g. '03 - Resources/AI/Transformers.md' or 'Transformers')",
                }
            },
            "required": ["note"],
        },
    },
    "domain_list": {
        "name": "domain_list",
        "description": "List notes in a specified PARA domain queue (inbox, projects, areas, resources, archives) sorted chronologically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Target domain: 'inbox', 'projects', 'areas', 'resources', 'archives'",
                    "default": "inbox",
                }
            },
        },
    },
    "note_move": {
        "name": "note_move",
        "description": "Relocate a note into a target PARA destination (e.g. 'projects/Apollo', 'areas/Finance') with automatic OKF metadata updates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "Relative path, title, or filename of the note to move",
                },
                "target": {
                    "type": "string",
                    "description": "Destination PARA domain or subpath (e.g. 'projects', 'projects/Apollo', 'areas/Health')",
                },
                "description": {
                    "type": "string",
                    "description": "Optional 15-35 word executive summary (TL;DR) to inject into frontmatter during relocation",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, simulates the move and returns the planned destination and metadata updates without modifying files on disk.",
                },
            },
            "required": ["note", "target"],
        },
    },
    "note_refactor": {
        "name": "note_refactor",
        "description": "Atomically rename a note and rewrite all referencing inbound Wikilinks and Markdown links across the vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Existing note path, filename, or title to rename (e.g. '01 - Projects/Old Name.md')",
                },
                "target": {
                    "type": "string",
                    "description": "New note title or target relative path (e.g. 'New Name' or '01 - Projects/New Name.md')",
                },
                "links_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, rewrite referencing links without renaming or modifying the source file on disk.",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, preview planned file rename and link rewrites without modifying files on disk.",
                },
            },
            "required": ["source", "target"],
        },
    },
    "note_archive": {
        "name": "note_archive",
        "description": "Retire an active or evergreen note into 04 - Archives/ with status: archived.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "Relative path, title, or filename of the note to archive",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, simulates retirement and returns the planned archive destination without modifying files on disk.",
                },
            },
            "required": ["note"],
        },
    },
    "note_verify": {
        "name": "note_verify",
        "description": "Record a verification event on a note's frontmatter, updating its computed OKF trust tier.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note_path": {
                    "type": "string",
                    "description": "Relative path to note file within vault (e.g. '03 - Resources/Raft Consensus.md')",
                },
                "note": {
                    "type": "string",
                    "description": "Alias for note_path. Relative path, filename, or title of note to verify.",
                },
                "actor": {
                    "type": "string",
                    "description": "Actor identifier (<producer>/<version>, human:<id>, or process:<id>). Defaults to system user.",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, preview verification without writing to disk.",
                },
            },
            "required": ["note_path"],
        },
    },
    "vault_search": {
        "name": "vault_search",
        "description": "High-velocity full-text BM25 search across vault notes with cognitive ranking (domain, trust, staleness, and graph centrality) and faceted metadata filtering.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query keywords or regex pattern",
                },
                "domain": {
                    "type": "string",
                    "description": "Filter by domain (inbox, projects, areas, resources, archives)",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by OKF lifecycle status (unprocessed, active, evergreen, archived)",
                },
                "type": {
                    "type": "string",
                    "description": "Filter by OKF artifact type (inbox, project-note, area-note, resource-note, archive-note)",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 20, max: 100)",
                    "default": 20,
                },
                "snippets": {
                    "type": "boolean",
                    "description": "Include matching contextual snippets in results (default: false)",
                    "default": False,
                },
                "trust_tier": {
                    "type": "string",
                    "enum": ["unverified", "machine-confirmed", "human-reviewed"],
                    "description": "Filter results by computed OKF trust tier.",
                },
                "fresh_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, exclude notes whose stale_after instant has passed.",
                },
                "json": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, return structured JSON payload with note metadata, trust tier, and active backlink counts.",
                },
            },
        },
    },
    "vault_links": {
        "name": "vault_links",
        "description": "Traverse vault Wikilinks/backlinks, audit broken references, or detect isolated orphan notes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "Target note to inspect outbound links or query backlinks",
                },
                "mode": {
                    "type": "string",
                    "enum": [
                        "outbound",
                        "backlinks",
                        "broken",
                        "orphans",
                        "unreferenced",
                    ],
                    "description": "Link inspection mode (default: 'outbound')",
                    "default": "outbound",
                },
                "depth": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3,
                    "default": 1,
                    "description": "Traversal depth for 'outbound' or 'backlinks' modes (1 = direct, 2 = 2-hop neighborhood)",
                },
                "headings": {
                    "type": "boolean",
                    "description": "When mode='broken', also validate sub-heading anchors (#Heading)",
                    "default": False,
                },
                "domain": {
                    "type": "string",
                    "description": "Filter operations to specified PARA domain",
                },
            },
        },
    },
    "vault_lint": {
        "name": "vault_lint",
        "description": "Audit notes for Open Knowledge Format (OKF) schema compliance and domain-lifecycle alignment, with optional auto-fix.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "Optional single note path or filename (default: vault-wide)",
                },
                "domain": {
                    "type": "string",
                    "description": "Optional domain filter (inbox, projects, areas, resources, archives)",
                },
                "fix": {
                    "type": "boolean",
                    "description": "Automatically repair fixable schema defects and domain misalignments in-place",
                    "default": False,
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "When fix=true, preview planned repairs without altering files on disk",
                    "default": False,
                },
                "strict": {
                    "type": "boolean",
                    "description": "Promote schema warnings (such as missing descriptions in 01-03) to errors",
                    "default": False,
                },
            },
        },
    },
}
