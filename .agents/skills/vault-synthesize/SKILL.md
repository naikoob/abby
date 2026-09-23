---
name: "vault-synthesize"
description: "Unified playbook for FIFO inbox triage, PARA routing, atomic concept decomposition into 03 - Resources/ with MOC mesh connectivity, and pre-archive project distillation."
---

# Vault Triage & Synthesis Playbook

This playbook is the single source of truth for processing raw notes in `00 - Inbox/` (FIFO triage and atomic concept synthesis) and distilling evergreen knowledge from completed `01 - Projects/` initiatives prior to archival.

## Linked Editorial & Structural Standards (Mandatory Read)

Before authoring descriptions, tags, or atomic notes, load via `view_file`:
1. **[`STYLE.md`](../../../STYLE.md)**: Direct analytical active voice, 15–35 word `description` (zero *"This note covers..."* filler), flat kebab-case YAML tags without `#` prefixes, and max `###` (H3) heading depth.
2. **[`05 - Assets/Templates/`](../../../05%20-%20Assets/Templates)**:
   - [`Concept Note.md`](../../../05%20-%20Assets/Templates/Concept%20Note.md) (`# <Title>`, `## Core Thesis`, `## Mechanism & Elaboration`, `## Trade-offs & Boundaries`, `## Connected Concepts`)
   - [`Decision Record.md`](../../../05%20-%20Assets/Templates/Decision%20Record.md) (`# ADR: <Title>`, `## Status`, `## Context & Problem Statement`, `## Options Considered`, `## Decision Outcome`, `## Consequences`)
   - [`Project Note.md`](../../../05%20-%20Assets/Templates/Project%20Note.md) / [`Area Note.md`](../../../05%20-%20Assets/Templates/Area%20Note.md)

## User Input

```text
$ARGUMENTS
```

Optional arguments:
- `note`: Specific note path/title to process (default: process `00 - Inbox/` queue in FIFO order).
- `limit`: Maximum inbox notes to process in one batch (default: `10`).
- `category`: Target category subfolder in `03 - Resources/` for synthesized concepts (e.g., `Architecture`, `AI`, `Systems`).
- `dry_run`: Preview relocations without mutating disk (default: `false`).

---

## Workflow Steps

### 1. Fetch Queue & Inspect Note
- If processing the inbox queue, list notes in chronological creation order:
  - MCP: `domain_list(domain="inbox")` | CLI: `abby list inbox`
- Read the structured note payload:
  - MCP: `note_read(note="<note>")`

### 2. Complexity Branch: Single-Topic vs. Multi-Concept Brain Dump
Inspect the note body and classify it into **Path A (Direct PARA Routing)** or **Path B (Atomic Decomposition)**:
- **Choose Path A** if the note represents a single coherent project update, ongoing area standard, single reference topic, or completed item.
- **Choose Path B** if the note is an unstructured brain dump, meeting transcript, or research log containing **multiple distinct ideas, architectures, or decisions** (or if distilling a completed `01 - Projects/` folder before archiving).

---

### Path A: Direct PARA Routing & Verification (Single-Topic Notes)

1. **Select Target PARA Domain**:
   - `01 - Projects/<Name>/` (`target="projects/<Name>"`): Finite initiatives with target milestones (`type: project-note`, `status: active`).
   - `02 - Areas/<Domain>/` (`target="areas/<Domain>"`): Long-term ongoing responsibilities (`type: area-note`, `status: active`).
   - `03 - Resources/<Category>/` (`target="resources/<Category>"`): Single-topic evergreen reference (`type: resource-note`, `status: evergreen`).
   - `04 - Archives/`: Already completed or superseded items (`note_archive(note="<note>", dry_run=False)`).
2. **Relocate with 15–35 Word Executive Summary**:
   - Author a 15–35 word active-voice `description` (per [`STYLE.md`](../../../STYLE.md)) if missing so the note passes `vault_lint(strict=True)`:
     ```python
     note_move(
         note="<note>",
         target="<destination>",
         description="<15-35 word active-voice summary>",
         dry_run=False,
     )
     ```
3. **Stamp Machine Confirmation**:
   - Record provenance attestation so `trust_tier` evaluates to `machine-confirmed`:
     ```python
     note_verify(
         note_path="<destination_path>",
         actor="abby/agent:steward",
         dry_run=False,
     )
     ```

---

### Path B: Atomic Decomposition & Mesh Weaving (Multi-Concept Notes)

1. **Pre-Creation Deduplication & Hub Discovery**:
   - For each candidate concept extracted from the source note, search `03 - Resources/`:
     ```python
     vault_search(query="<concept>", domain="resources", snippets=True)
     ```
   - **Deduplicate**: If an authoritative note already exists, enrich or link to it instead of creating a duplicate.
   - **Identify Parent Hub**: Select the highest-`active_backlinks` concept note or Map of Content (`[[<Topic> MOC]]`) from search results to serve as the parent graph anchor.
2. **Two-Step Atomic Crystallization (`note_capture` $\rightarrow$ `note_move`)**:
   - **Step 2a — Stage in `00 - Inbox/` with Provenance**:
     ```python
     note_capture(
         title="<Concept Title>",
         body="<Markdown body following Concept Note.md or Decision Record.md skeleton>",
         description="<15-35 word active-voice executive summary>",
         tags=["concept", "<kebab-case-topic>"],
         generated={"by": "abby/agent:steward", "at": "<ISO 8601 UTC>"},
         verified=[{"by": "abby/agent:steward", "at": "<ISO 8601 UTC>"}],
         sources=[{"resource": "<Source Note Path>", "title": "<Source Title>"}],
     )
     ```
   - **Step 2b — Graduate to `03 - Resources/<Category>/`**:
     ```python
     note_move(
         note="00 - Inbox/<Concept Title>.md",
         target="resources/<Category>",
         description="<15-35 word active-voice executive summary>",
         dry_run=False,
     )
     ```
3. **Bidirectional Mesh Attachment & Source Retirement**:
   - Link the new concept note bidirectionally (`[[Note Title|display alias]]`) to related concepts and ensure at least one inbound Wikilink from its parent hub or `[[<Topic> MOC]]` (scaffold a `[[<Topic> MOC]]` when a topical cluster reaches $\ge 5$ notes).
   - Once all concepts are graduated and linked, archive the raw source note (or completed project note):
     ```python
     note_archive(note="<Source Note Path>", dry_run=False)
     ```

---

### 3. Handover Breadcrumb & Structured Report
- If any active `01 - Projects/` or `02 - Areas/` note was updated, append an in-note `## Handover Summary` breadcrumb per `AGENTS.md §5`.
- Return this summary to the caller:

```markdown
### Triage & Synthesis Summary
- **Notes Processed**: <count>
- **Direct PARA Relocations (Path A)**:
  - `00 - Inbox/<Note>.md` -> `<Destination>` (`machine-confirmed`)
- **Atomic Concepts Crystallized (Path B)**:
  - `03 - Resources/<Category>/<Concept>.md` (Linked to hub `[[<Hub Note>]]`)
- **Archived Sources**:
  - `<Source Note>` -> `04 - Archives/<Source Note>`
```
