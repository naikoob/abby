"""Template utilities, vault-first resolution, and default note skeletons for Abby."""

from __future__ import annotations

from pathlib import Path
from typing import Final, Optional

# Minimal, compliant OKF v0.2 fallback starter skeletons for standalone execution
FALLBACK_STYLE_CONTENT: Final[str] = """# Abby Personal Style & Vault Preferences

## 1. User Profile & Context
- **Role**: Software Engineer & Knowledge Worker
- **Primary Tooling**: Obsidian, Google Antigravity, Claude Desktop, Cursor

## 2. Voice, Tone & Cadence
- **Tone**: Direct, concise, technical, active-voice. Anti-slop.
- **Max Heading Depth**: `###` (H3).

## 3. Formatting & Obsidian Markdown
- Use Obsidian Wikilinks: `[[Note Title]]` or `[[Note Title#Heading Anchor|alias]]`.
- Callouts: Use standard Obsidian callouts (`> [!NOTE]`, `> [!IMPORTANT]`, `> [!WARNING]`).

## 4. Taxonomy & Tagging
- Flat kebab-case tags only without `#` prefix (e.g. `deep-learning`).

## 5. Domain Lexicon & Shorthand
| Term | Meaning |
|---|---|
| OKF | Open Knowledge Format (YAML frontmatter standard for Abby notes) |
| PARA | Projects, Areas, Resources, Archives |
| FTS5 | SQLite Full-Text Search 5 |
"""

FALLBACK_AGENTS_CONTENT: Final[str] = """# Abby Knowledge Vault: Agent Operating Guide & Protocol

Authoritative operating model, architectural boundaries, metadata standards, and tooling interfaces for AI agents collaborating in the Abby Knowledge Vault.

---

## 1. Operating Tenets & The Air-Gap Persona Model

Abby enforces strict separation between human-curated knowledge and technical automation:
- **Never Corrupt Human Thought**: Notes, formatting, Wikilinks, Obsidian block references (`^blockid`), and custom YAML properties must be preserved non-destructively.
- **Deterministic Tooling**: Vault mutations occur through Abby's typed MCP and CLI tools, never through ad-hoc file writing.
- **Consolidated Personas**:
  - **Root Conversational Agent**: Grounded Q&A (`vault_search`, `vault_links`) and Fast Inbox Capture (`note_capture`).
  - **Knowledge Steward (`steward.md`)**: Plane 1 (`00`–`05`) FIFO triage, atomic synthesis (`vault-synthesize`), and curation (`vault-curate`).
  - **Vault Technician (`technician.md`)**: Plane 2 (`.system/`) engine, FTS5 cache, and test runner (`vault-technician`).

---

## 2. Directory Taxonomy & Domain Constraints (PARA+)

| Directory | Role & Constraints | Domain |
|---|---|---|
| `00 - Inbox/` | Fast note staging. All new notes enter here. | Knowledge Domain |
| `01 - Projects/` | Time-bound active initiatives with defined outcomes. Distill to `03` before archiving. | Knowledge Domain |
| `02 - Areas/` | Long-term ongoing responsibilities and operational domains. | Knowledge Domain |
| `03 - Resources/` | Evergreen knowledge, concepts, research, cheatsheets, and reference. | Knowledge Domain |
| `04 - Archives/` | Completed projects, inactive areas, or retired notes. | Knowledge Domain |
| `05 - Assets/` | Static attachments, diagrams, images, and starter templates (`Templates/`). | Knowledge Domain |
| `.system/` | Self-contained Python engine, CLI utilities, and SQLite cache (`.system/cache/`). | System Domain |
| `.obsidian/` | Obsidian client UI state and plugins. **Forbidden to agents** unless tasked. | System Domain |
| `.agents/` | Reusable skills (`.agents/skills/`) and sub-agents (`.agents/subagents/`). | System Domain |
| `AGENTS.md` | This authoritative root agent guide. | System Domain |
"""

FALLBACK_TEMPLATES: Final[dict[str, str]] = {
    "Project Note.md": """---
title: "{{title}}"
description: "Executive summary of project outcome and scope."
created: "{{date}}"
updated: "{{date}}"
type: project-note
status: active
tags:
  - project
---

# {{title}}

## Desired Outcome
<!-- What does success look like when this project is completed? -->

## Milestones & Horizon
- [ ] Milestone 1 (Target: YYYY-MM-DD)
- [ ] Milestone 2 (Target: YYYY-MM-DD)

## Tasks & Deliverables
- [ ] Task 1
- [ ] Task 2

## Key Decisions & Log
- YYYY-MM-DD: Initial project kickoff.

## Related Context
- Area: [[02 - Areas/Relevant Area]]
- Resources: [[03 - Resources/Relevant Concept]]

---
## Handover Summary
- **Updated**: {{date}}
- **Actor**: Human / Agent
- **Current Progress**: Project initialized.
- **Open Questions**: None.
- **Next Actions**: Execute Milestone 1.
---
""",
    "Area Note.md": """---
title: "{{title}}"
description: "Long-term standards and operational scope of this area."
created: "{{date}}"
updated: "{{date}}"
type: area-note
status: active
tags:
  - area
---

# {{title}}

## Mission & Standards
<!-- Long-term purpose of this area and definition of operational health -->

## Operating Routines
- [ ] Routine 1 (Weekly / Monthly)
- [ ] Routine 2

## Key Indicators & Health
- Metric/Indicator 1

## Active Projects
- [[01 - Projects/Active Project]]

## Curated Resources
- [[03 - Resources/Reference Note]]
""",
    "Concept Note.md": """---
title: "{{title}}"
description: "Atomic principle and conceptual definition."
created: "{{date}}"
updated: "{{date}}"
type: resource-note
status: evergreen
tags:
  - concept
---

# {{title}}

## Core Thesis
<!-- 1-2 sentence concise definition or atomic principle -->

## Mechanism & Elaboration
<!-- How it works, context, mechanics, and nuance -->

## Trade-offs & Boundaries
<!-- When does this concept break down or fail to apply? -->

## Connected Concepts
- [[03 - Resources/Related Concept A]]
- [[03 - Resources/Related Concept B]]
""",
    "Meeting Note.md": """---
title: "{{title}}"
description: "Meeting discussion overview and key decisions."
created: "{{date}}"
updated: "{{date}}"
type: inbox
status: unprocessed
tags:
  - meeting
---

# {{title}}

## Overview
- **Date**: {{date}}
- **Participants**: 
- **Topic**: 

## Discussion & Highlights
- Point 1
- Point 2

## Decisions Made
- Decision 1

## Action Items
- [ ] Task 1 (@assignee)
- [ ] Task 2 (@assignee)
""",
    "Decision Record.md": """---
title: "ADR: {{title}}"
description: "Architecture decision record summary and chosen option."
created: "{{date}}"
updated: "{{date}}"
type: resource-note
status: evergreen
tags:
  - decision
  - adr
---

# ADR: {{title}}

## Status
Proposed | Accepted | Deprecated | Superseded

## Context & Problem Statement
<!-- What problem are we solving, and why is this decision needed? -->

## Options Considered
1. **Option A**: Description, pros, cons.
2. **Option B**: Description, pros, cons.

## Decision Outcome
**Chosen**: Option A because ...

## Consequences
- **Positive**: 
- **Negative**: 
- **Neutral**: 
""",
}


def get_enclosing_vault_root() -> Optional[Path]:
    """Locate enclosing vault root by checking ancestor directories for characteristic markers."""
    current = Path(__file__).resolve().parent
    for ancestor in current.parents:
        if (ancestor / ".system").is_dir() and (
            (ancestor / "05 - Assets" / "Templates").is_dir()
            or (ancestor / "AGENTS.md").is_file()
        ):
            return ancestor
    return None


def get_assets_dir(vault_root: Optional[Path] = None) -> Path:
    """Return the assets directory (05 - Assets) for target or enclosing vault."""
    root = vault_root or get_enclosing_vault_root()
    if root is not None:
        return root / "05 - Assets"
    return Path.cwd() / "05 - Assets"


def get_default_inbox_body(title: str) -> str:
    """Return default clean placeholder content for a freshly captured inbox note."""
    return f"# {title}\n\n<!-- Captured via Abby CLI. Capture details, notes, or thoughts below. -->\n"


def get_default_style_content(
    source_vault_root: Optional[Path] = None,
    *,
    vault_root: Optional[Path] = None,
) -> str:
    """Return default content for STYLE.md at the vault root.

    Resolves from source_vault_root or enclosing master vault root, falling back to built-in defaults.
    """
    root = source_vault_root or vault_root or get_enclosing_vault_root()
    if root is not None:
        style_file = root / "STYLE.md"
        if style_file.is_file():
            return style_file.read_text(encoding="utf-8")
    return FALLBACK_STYLE_CONTENT


def get_default_agents_content(
    source_vault_root: Optional[Path] = None,
    *,
    vault_root: Optional[Path] = None,
) -> str:
    """Return default content for AGENTS.md at the vault root.

    Resolves from source_vault_root or enclosing master vault root, falling back to built-in defaults.
    """
    root = source_vault_root or vault_root or get_enclosing_vault_root()
    if root is not None:
        agents_path = root / "AGENTS.md"
        if agents_path.is_file():
            return agents_path.read_text(encoding="utf-8")
    return FALLBACK_AGENTS_CONTENT


def get_canonical_templates(
    source_vault_root: Optional[Path] = None,
    *,
    vault_root: Optional[Path] = None,
) -> dict[str, str]:
    """Return dictionary mapping template filenames to their Markdown content.

    Discovers canonical templates from master enclosing vault's 05 - Assets/Templates,
    falling back to built-in templates if none exist on disk.
    """
    root = source_vault_root or vault_root or get_enclosing_vault_root()
    if root is not None:
        templates_dir = root / "05 - Assets" / "Templates"
        if templates_dir.is_dir():
            templates: dict[str, str] = {}
            for file_path in sorted(templates_dir.glob("*.md")):
                templates[file_path.name] = file_path.read_text(encoding="utf-8")
            if templates:
                return templates
    return dict(FALLBACK_TEMPLATES)
