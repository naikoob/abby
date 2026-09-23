---
title: "Quick Start Guide"
description: "Action-oriented quick start guide for the Abby Knowledge Vault, providing core workflows, practical lifecycle steps, and ready-to-use Antigravity prompts for daily capture, research, and curation."
created: "2026-09-23T16:52:33"
type: resource-note
status: evergreen
tags:
  - inbox
  - quick-start
  - workflow
  - prompts
  - reference
updated: 2026-09-23T16:52:43
verified:
  - by: abby/agent:steward
    at: "2026-09-23T08:52:46Z"
---
## 5-Minute Mental Model

The Abby Knowledge Vault is designed for pair work between you and AI agents in Antigravity. You think, read, and write in Obsidian Markdown; Antigravity retrieves, indexes, and maintains structure at machine speed.

The vault organizes all information into five folders (the PARA+ taxonomy):
- **`00 - Inbox/`**: Your staging buffer. Throw thoughts, raw meeting transcripts, and bookmarks here without worrying about formatting.
- **`01 - Projects/`**: Time-bound efforts with deliverables (e.g., client work, feature launches).
- **`02 - Areas/`**: Ongoing domains and responsibilities without end dates (e.g., DevOps, Health, Architecture).
- **`03 - Resources/`**: Evergreen reference knowledge, atomic concepts, and architectural decisions.
- **`04 - Archives/`**: Completed or inactive material preserved for historical reference.

> [!TIP]
> You do not need to memorize CLI commands or YAML schemas. Type naturally in Antigravity chat, and Antigravity executes the appropriate operations under the hood.

---

## Daily Workflows & Antigravity Prompts

Copy, adapt, and run these prompts directly in Antigravity.

### 1. Capturing Ideas & Raw Notes

Capture fleeting ideas instantly without letting metadata formatting slow down your train of thought.

**Single-Concept Capture**
> "Capture a note in 00 - Inbox titled 'Consensus Leases' summarizing how lease-based leaders eliminate split-brain read bottlenecks."

**Raw Meeting or Brain Dump Staging**
> "Here are my rough notes from today's engineering sync:
> [paste notes]
> Clean them up, format with bullet points and action items, and save as a new note in 00 - Inbox titled 'Telemetry Engine Sync'."

---

### 2. Triaging & Organizing the Inbox

Turn raw staging notes into well-structured, permanent knowledge records.

**Review & Route the Inbox**
> "List all unprocessed notes in 00 - Inbox. For each note, propose the best PARA destination (Projects, Areas, or Resources), a 15–35 word active-voice description, and tags. Show me the plan before moving."

**Distill Brain Dumps into Atomic Concepts**
> "Process the note 'Telemetry Engine Sync' in 00 - Inbox:
> 1. Extract any generalizable architecture patterns into atomic notes in 03 - Resources/.
> 2. Route the meeting action items into our active project in 01 - Projects/.
> 3. Link the new resource notes together with Wikilinks."

---

### 3. Searching & Researching Your Vault

Retrieve grounded facts from your notes without hallucination. Antigravity searches your vault's SQLite FTS5 index before answering.

**Factual Vault Q&A**
> "Search my vault for our decisions on SQLite WAL mode and connection pooling. Cite the specific notes where these decisions are recorded."

**Graph Traversal & Topic Synthesis**
> "Traverse notes connected to 'Distributed Systems' up to 2 hops deep. Synthesize how our consensus model, caching layer, and lease strategies interact."

**Filter by Verified Trust**
> "Search for human-reviewed notes on data migration protocols. Exclude unverified drafts or stale notes."

---

### 4. Managing Projects from Kickoff to Archival

Keep project workspaces clean and capture reusable insights before closing initiatives.

**Project Kickoff**
> "Create a new project note in 01 - Projects titled 'Search Optimization' with target outcomes, deliverables, and initial milestones."

**Session Handover Breadcrumb**
> "I'm stopping work on the 'Search Optimization' project for today. Audit our recent progress and append a Handover Summary section with current status, open questions, and next actions."

**Project Completion & Distillation**
> "We just completed the 'Search Optimization' project.
> 1. Distill any reusable patterns and architectural decisions into permanent notes in 03 - Resources/.
> 2. Move the project note to 04 - Archives."

---

### 5. Maintaining Vault Health & Hygiene

Keep your graph connected, links working, and frontmatter valid.

**Vault Health Audit**
> "Run a full health check on the vault. Check for broken Wikilinks, missing heading anchors, and frontmatter schema issues. Preview the findings."

**Automated Remediation**
> "Fix any malformed tags or schema warnings across the vault. Run in dry-run mode first so I can preview the changes."

**Safe Renaming Across the Graph**
> "Rename the note 'Cache Design' to 'SQLite FTS5 Architecture' and safely update all inbound links across referencing notes."

---

## Three Essential Habits

1. **Capture first, organize second**: Drop thoughts in `00 - Inbox/` with zero friction. Let Antigravity handle schema properties and PARA graduation later.
2. **Distill before archiving**: When finishing a project, extract reusable principles into `03 - Resources/` so your knowledge compounds over time.
3. **Link generously**: Use `[[Note Title|alias]]` to connect related concepts. High-signal links allow Antigravity to traverse multi-hop contexts effectively.

---

## Further Reading

- [`README.md`](../README.md): In-depth technical architecture, complete CLI command manual, OKF v0.2 schema definitions, and trust models.
