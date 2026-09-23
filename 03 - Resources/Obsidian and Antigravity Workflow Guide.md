---
title: "Obsidian and Antigravity Workflow Guide"
description: "Practical guide for pairing Obsidian with Antigravity, detailing vault settings, graph visualization, OKF Dataview dashboards, and automated human-AI triage workflows."
created: "2026-09-23T18:26:43"
type: resource-note
status: evergreen
tags:
  - inbox
  - obsidian
  - antigravity
  - workflow
  - dataview
  - reference
updated: 2026-09-23T18:26:56
verified:
  - by: abby/agent:steward
    at: "2026-09-23T10:26:59Z"
---
## The Human-Agent Co-Habitation Model

The Abby Knowledge Vault operates on a dual-audience architecture:
- **Obsidian** is your human workspace: fluid Markdown editing, rich local search, visual graph canvas, and reading comfort.
- **Antigravity** is your automated co-pilot: structured MCP tools, deterministic SQLite FTS5 search, atomic note moves, and graph link refactoring.

### Division of Labor

| Workflow Phase | Human Role (Obsidian) | Antigravity Role (AI Agent) |
|---|---|---|
| **Capture** | Quick-capture rough thoughts, transcripts, and meeting dumps into `00 - Inbox/`. | Ingests external articles, cleans transcripts, and generates structured inbox notes. |
| **Triage & Routing** | Reviews proposed classifications and approves permanent note destinations. | Scans inbox, suggests PARA routing, drafts 15–35 word descriptions, and moves notes atomically. |
| **Research & Synthesis** | Reads synthesized hubs, browses MOCs, and navigates backlinks. | Traverses multi-hop link graphs, filters by trust tier, and synthesizes answers across notes. |
| **Maintenance** | Verifies note contents (`abby verify --by human:<id>`) and makes editorial decisions. | Detects broken Wikilinks, repairs malformed YAML tags, and rebuilds FTS5 search indices. |

> [!NOTE]
> The **Constitutional Air-Gap** keeps this collaboration safe. You can freely edit any note in `00` through `05` inside Obsidian. Antigravity will never overwrite files without atomic safety guarantees, and system engine files in `.system/` remain isolated from note contents.

---

## Recommended Obsidian Configuration

Configure these options in Obsidian under **Settings (`Ctrl+,` / `Cmd+,`)** to align native editor behavior with Abby:

### Files & Links Preferences

- **Default location for new notes**: `In the folder specified below` $\rightarrow$ set to `00 - Inbox`  
  *(Ensures `Ctrl+N` rapid captures always land in the triage queue).*
- **New link format**: `Shortest path when possible`
- **Use `[[Wikilinks]]`**: **ON**  
  *(Mandatory for Abby's graph traversal, link diagnostics, and cognitive centrality scoring).*
- **Default location for new attachments**: `In the folder specified below` $\rightarrow$ set to `05 - Assets/Attachments`
- **Excluded files (`userIgnoreFilters`)**: Add `.system` and `.agents`  
  *(Prevents technical engine code, system specs, and subagent prompts from cluttering Quick Switcher `Ctrl+O` and search).*

### Graph View Configuration & Noise Filtering

In Obsidian's **Graph View (`Ctrl+G`)**, configure display settings and filters to isolate human knowledge from system automation and root documentation:

- **Filter Search Query (Recommended — Inclusive PARA Whitelist)**:
  ```text
  path:"00 - Inbox" OR path:"01 - Projects" OR path:"02 - Areas" OR path:"03 - Resources" OR path:"04 - Archives"
  ```
  *(Or concise regex: `path:/^0[0-4] -/`). This is the cleanest and most robust filter: it ensures **only** genuine notes in your five PARA domains appear on the graph, automatically filtering out root system documentation (`README.md`, `AGENTS.md`, `STYLE.md`), starter templates in `05 - Assets/Templates/`, and hidden automation files (`.system/`, `.agents/`).*
- **Active Knowledge Graph (Excluding Archives)**:
  ```text
  path:"00 - Inbox" OR path:"01 - Projects" OR path:"02 - Areas" OR path:"03 - Resources"
  ```
- **Directional Arrows**: Toggle **Arrows: ON** to show link citation vectors toward concept hubs.
- **Node Size Scaling**: Increase **Node Size by Link Count** (`1.35x`) so central Maps of Content (MOCs) visually expand.
- **Forces Tuning**: Set **Repel Strength** (14) and **Link Distance** (250) to allow PARA clusters to separate cleanly without collapsing into an overlapping sphere.

| Domain Group | Search Filter Query | Recommended Color | Role in Vault |
|---|---|---|---|
| **Inbox** | `path:"00 - Inbox"` | Amber (`#f59e0b`) | Unprocessed staging buffer |
| **Projects** | `path:"01 - Projects"` | Sky Blue (`#0ea5e9`) | Active time-bound deliverables |
| **Areas** | `path:"02 - Areas"` | Emerald (`#10b981`) | Long-term operational domains |
| **Resources** | `path:"03 - Resources"` | Purple (`#8b5cf6`) | Evergreen concepts & ADRs |
| **Archives** | `path:"04 - Archives"` | Slate Gray (`#64748b`) | Completed historical records |

> [!TIP]
> Use **Local Graph View** (`More options -> Open linked view -> Open local graph`) when drafting evergreen notes in `03 - Resources/`. Set depth to `1` or `2` to explore immediate conceptual neighborhoods without full-vault clutter.

---

## Dataview Dashboards for OKF Metadata

The community plugin **Dataview** translates Abby's Open Knowledge Format (OKF v0.2) YAML metadata into dynamic tables and task lists inside Obsidian.

### Active Projects Dashboard

Insert into your personal dashboard or root index note to monitor current initiatives:

````markdown
```dataview
TABLE description AS "Target Outcome", updated AS "Last Active"
FROM "01 - Projects"
WHERE status = "active"
SORT updated DESC
```
````

### Inbox Triage Queue

Displays notes waiting in `00 - Inbox/` in chronological order:

````markdown
```dataview
TABLE created AS "Captured", tags AS "Tags"
FROM "00 - Inbox"
WHERE status = "unprocessed" OR !status
SORT file.ctime ASC
```
````

### Stale Knowledge Watcher

Surfaces notes whose `stale_after` expiration timestamp has passed, alerting you to review or re-verify them:

````markdown
```dataview
TABLE description AS "Summary", stale_after AS "Expired On"
FROM "01 - Projects" OR "02 - Areas" OR "03 - Resources"
WHERE stale_after AND date(stale_after) < date(today)
SORT stale_after ASC
```
````

### High-Centrality Concept Hubs

Ranks resource notes by their number of active inbound backlinks:

````markdown
```dataview
TABLE description AS "Core Thesis", length(file.inlinks) AS "Inbound Links"
FROM "03 - Resources"
WHERE type = "resource-note"
SORT length(file.inlinks) DESC
LIMIT 25
```
````

---

## The Weekly Human-AI Workflow Rhythm

A sustainable routine for keeping the vault clean without administrative friction:

### Daily Rapid Capture
- Press `Ctrl+N` in Obsidian to quickly capture a meeting snippet or bookmark into `00 - Inbox/`.
- Alternatively, prompt Antigravity: *"Capture an idea titled 'Distributed Leases' into Inbox."*

### Periodic Triage & Distillation
- Once or twice a week, review your Inbox Dataview queue.
- Tell Antigravity: *"Triage the notes in 00 - Inbox, propose PARA folders and descriptions, and show me the plan before moving."*
- When wrapping up a project in `01 - Projects/`, ask Antigravity: *"Distill any reusable architectures from this project into 03 - Resources, then archive the project note."*

### Graph Health Maintenance
- Run a quick health check via Antigravity: *"Audit broken links and rebuild the search cache."*
- Antigravity scans for dangling Wikilinks, validates heading anchors, and syncs the SQLite FTS5 database.

---

## Connected References

- [[Quick Start Guide|Quick Start Guide]]: Actionable cheat sheet with ready-to-run Antigravity prompts.
- [`README.md`](../README.md): Full technical specification, CLI command reference, and MCP server setup.
