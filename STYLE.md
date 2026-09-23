# Abby Personal Style & Vault Preferences

## 1. User Profile & Context
- **Role & Background**: Knowledge worker / Researcher / Engineer
- **Assumed Knowledge**: Technical literacy, Markdown navigation, standard software and systems terminology.
- **Guidance**: Skip generic introductory tutorials or definitions; focus directly on architectural, operational, or conceptual essence.

## 2. Voice, Tone & Cadence
- **Tone**: Direct, analytical, objective, and dense.
- **Perspective**: Active voice (impersonal or first-person when recording decisions).
- **Executive Summaries (`description`)**: 15–35 words in active voice capturing the note's essence, outcome, or core thesis. Zero fluff or introductory filler (no "This note covers...", no "In this document...").
- **Anti-Patterns**: 
  - No conversational filler ("In this note, we will explore...", "It is important to remember...").
  - No rhetorical questions or unprompted motivational conclusions.
  - No excessive hedging.

## 3. Formatting & Obsidian Markdown
- **Max Heading Depth**: Max `###` (H3). Keep heading titles punchy.
- **Lists vs Prose**: Use bullet points for facts, steps, and options; use short (2-3 sentence) paragraphs for conceptual synthesis.
- **Callouts**:
  - `> [!NOTE]` for caveats and contextual side notes.
  - `> [!IMPORTANT]` for major decisions or breaking changes.
  - `> [!TIP]` for optimizations and best practices.
- **Wikilinks**: High-signal linking. Link concepts on first mention using `[[Note Title|display alias]]` to maintain natural prose flow.
- **Templates**: Standard note templates reside in `05 - Assets/Templates/`.

## 4. Taxonomy & Tagging
- **Tag Style**: Flat, kebab-case without `#` prefix (e.g., `machine-learning`, `system-design`).
- **Forbidden**: Never use leading `#` prefix inside YAML frontmatter. Never use spaces, camelCase, or snake_case.
- **Core Lifecycle Tags**:
  - `seed`: Raw, unrefined initial capture note.
  - `concept`: Evergreen, atomic conceptual knowledge note.
  - `decision`: Architectural or strategic decision record.
  - `review`: Material requiring human evaluation or synthesis.

## 5. Domain Lexicon & Shorthand
| Term | Meaning |
|---|---|
| OKF | Open Knowledge Format (YAML frontmatter standard for Abby notes) |
| PARA | Projects, Areas, Resources, Archives |
| FTS5 | SQLite Full-Text Search 5 |
