"""Constants and domain definitions for Abby Knowledge Vault."""

from __future__ import annotations

from typing import Final

# Maximum title byte length to ensure filenames fit within OS 255-byte limits
MAX_TITLE_BYTES: Final[int] = 240

# Maximum attempts for unique collision resolution
MAX_COLLISION_ATTEMPTS: Final[int] = 1000

# Canonical directory names
DEFAULT_INBOX_DIR: Final[str] = "00 - Inbox"
DEFAULT_PROJECTS_DIR: Final[str] = "01 - Projects"
DEFAULT_AREAS_DIR: Final[str] = "02 - Areas"
DEFAULT_RESOURCES_DIR: Final[str] = "03 - Resources"
DEFAULT_ARCHIVES_DIR: Final[str] = "04 - Archives"
DEFAULT_ASSETS_DIR: Final[str] = "05 - Assets"

# Knowledge domain directories according to Constitution Principle II (PARA+)
KNOWLEDGE_DIRECTORIES: Final[tuple[str, ...]] = (
    DEFAULT_INBOX_DIR,
    DEFAULT_PROJECTS_DIR,
    DEFAULT_AREAS_DIR,
    DEFAULT_RESOURCES_DIR,
    DEFAULT_ARCHIVES_DIR,
    DEFAULT_ASSETS_DIR,
)

# System and tooling directories
SYSTEM_DIRECTORIES: Final[tuple[str, ...]] = (".system",)

# All directories required for a healthy, fully initialized vault
REQUIRED_DIRECTORIES: Final[tuple[str, ...]] = (
    *KNOWLEDGE_DIRECTORIES,
    *SYSTEM_DIRECTORIES,
)

# Default agent operating guide and protocol filename at vault root
DEFAULT_AGENTS_FILE_NAME: Final[str] = "AGENTS.md"

# Characteristic markers used to detect an Abby Knowledge Vault root
VAULT_MARKERS: Final[tuple[str, ...]] = (
    ".system",
    ".specify",
    DEFAULT_INBOX_DIR,
    DEFAULT_AGENTS_FILE_NAME,
)

# System runtime path relative to vault root
SYSTEM_SUBPATH: Final[str] = ".system/abby"

# Search cache directory and database paths relative to vault root
DEFAULT_CACHE_DIR: Final[str] = ".system/cache"
DEFAULT_CACHE_DB: Final[str] = ".system/cache/vault.db"

# Shorthand aliases mapped to canonical directory names
DOMAIN_ALIAS_MAP: Final[dict[str, str]] = {
    "inbox": DEFAULT_INBOX_DIR,
    "projects": DEFAULT_PROJECTS_DIR,
    "areas": DEFAULT_AREAS_DIR,
    "resources": DEFAULT_RESOURCES_DIR,
    "archives": DEFAULT_ARCHIVES_DIR,
}

# Domains eligible for note storage (excludes 05 - Assets and .system)
VALID_NOTE_DOMAINS: Final[tuple[str, ...]] = (
    DEFAULT_INBOX_DIR,
    DEFAULT_PROJECTS_DIR,
    DEFAULT_AREAS_DIR,
    DEFAULT_RESOURCES_DIR,
    DEFAULT_ARCHIVES_DIR,
)

# Default OKF lifecycle status when moving into a domain
DOMAIN_DEFAULT_STATUS: Final[dict[str, str]] = {
    DEFAULT_INBOX_DIR: "unprocessed",
    DEFAULT_PROJECTS_DIR: "active",
    DEFAULT_AREAS_DIR: "active",
    DEFAULT_RESOURCES_DIR: "evergreen",
    DEFAULT_ARCHIVES_DIR: "archived",
}

# Default OKF artifact type when moving into a domain
DOMAIN_DEFAULT_TYPE: Final[dict[str, str]] = {
    DEFAULT_INBOX_DIR: "inbox",
    DEFAULT_PROJECTS_DIR: "project-note",
    DEFAULT_AREAS_DIR: "area-note",
    DEFAULT_RESOURCES_DIR: "resource-note",
    DEFAULT_ARCHIVES_DIR: "archive-note",
}

# Common asset and media extensions stored in 05 - Assets
ASSET_EXTENSIONS: Final[tuple[str, ...]] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".bmp",
    ".ico",
    ".pdf",
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".mp4",
    ".mov",
    ".webm",
    ".zip",
    ".tar",
    ".gz",
)

# Obsidian Wikilink pattern: !?[[Target(#Heading)?(|Alias)?]]
# Group 1: ! (embed/transclusion)
# Group 2: Target title/path
# Group 3: Optional section/heading anchor
# Group 4: Optional display alias
WIKILINK_PATTERN: Final[str] = (
    r"(!?)\[\[([^\]|#\r\n]+)(?:#([^\]|\r\n]+))?(?:\|([^\]\r\n]+))?\]\]"
)

# Local relative Markdown link pattern: !?[Label](path ("title")?)
# Group 1: ! (embed)
# Group 2: Label / alt text
# Group 3: Target path / URL
# Group 4: Optional hover title
MARKDOWN_LINK_PATTERN: Final[str] = (
    r"(!?)\[([^\]\r\n]*)\]\(([^)\s\r\n]+)(?:\s+\"([^\"\r\n]*)\")?\)"
)

# Fenced code block pattern (``` or ~~~) and inline code pattern (`...`)
FENCED_CODE_BLOCK_PATTERN: Final[str] = (
    r"(```[^\n]*\n[\s\S]*?\n```|~~~[^\n]*\n[\s\S]*?\n~~~)"
)
INLINE_CODE_PATTERN: Final[str] = r"(`[^`\r\n]+`)"

# Default personalization and style guide filename at vault root
DEFAULT_STYLE_FILE_NAME: Final[str] = "STYLE.md"

# Default template directory relative to vault root
DEFAULT_TEMPLATES_SUBDIR: Final[str] = f"{DEFAULT_ASSETS_DIR}/Templates"

# Re-export default contents from package assets for backward compatibility
from abby.utils.templates import (  # noqa: E402
    get_canonical_templates,
    get_default_agents_content,
    get_default_style_content,
)

DEFAULT_STYLE_CONTENT: Final[str] = get_default_style_content()
DEFAULT_AGENTS_CONTENT: Final[str] = get_default_agents_content()
CANONICAL_TEMPLATES: Final[dict[str, str]] = get_canonical_templates()
