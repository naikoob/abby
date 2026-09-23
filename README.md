# Abby Knowledge Vault

Abby is a modern knowledge management vault designed for seamless, asynchronous co-habitation between **human users** (navigating the vault via **Obsidian**) and **AI agents** (operating via Google Antigravity, Claude Desktop, Cursor, or CLI).

---

## 1. Architecture & Air-Gap Operating Model

Abby enforces a strict boundary between human-curated knowledge (`00`–`05`) and technical automation (`.system/`, `.agents/`):

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ABBY REPOSITORY ROOT                            │
├──────────────────────────────────┬─────────────────────────────────────┤
│         KNOWLEDGE DOMAIN         │            SYSTEM DOMAIN            │
│             (00 - 05)            │         (.system, .agents)          │
├──────────────────────────────────┼─────────────────────────────────────┤
│  ROOT CONVERSATIONAL AGENT:      │  SYSTEM SUBAGENT:                   │
│  - Grounded Q&A & Graph Search   │  - Vault Technician (technician.md) │
│  - Fast Inbox Capture            │    (Engine, FTS5 cache, MCP, tests) │
│                                  │                                     │
│  KNOWLEDGE SUBAGENT:             │  ARCHITECTURE & SPECS:              │
│  - Knowledge Steward (steward.md)│  - .system/specs/DESIGN.md          │
│    (Triage, Synthesis, Curation) │  - .system/specs/SPECIFICATION.md   │
│                                  │                                     │
│  Writes strictly inside 00–05;   │  Writes strictly inside .system/    │
│  NEVER modifies .system/ code.   │  and .agents/. 0 mutations to       │
│                                  │  notes in 00–05.                    │
└──────────────────────────────────┴─────────────────────────────────────┘
```

### PARA+ Directory Taxonomy

| Directory | Role & Lifecycle Constraints | Domain |
| :--- | :--- | :--- |
| `00 - Inbox/` | Fast note staging (`type: inbox`, `status: unprocessed`). All new notes enter here. | Knowledge Domain |
| `01 - Projects/` | Time-bound initiatives with target outcomes (`type: project-note`, `status: active`). Distill to `03` before archiving. | Knowledge Domain |
| `02 - Areas/` | Long-term ongoing responsibilities and operational domains (`type: area-note`, `status: active`). | Knowledge Domain |
| `03 - Resources/` | Evergreen knowledge, atomic concepts, ADRs, and reference (`type: resource-note`, `status: evergreen`). | Knowledge Domain |
| `04 - Archives/` | Completed projects, inactive areas, or retired raw notes (`type: archive-note`, `status: archived`). | Knowledge Domain |
| `05 - Assets/` | Static attachments, diagrams, images, and starter templates (`05 - Assets/Templates/`). | Knowledge Domain |
| `.system/` | Self-contained Python 3.10+ stdlib engine (`.system/abby/`), SQLite FTS5 cache (`.system/cache/`), and living architecture specs (`.system/specs/`). | System Domain |
| `.agents/` | Consolidated workflow skills (`.agents/skills/`) and air-gapped subagents (`.agents/subagents/`). | System Domain |
| `.obsidian/` | Obsidian client UI state and plugins. Treated as human-interface state. | System Domain |

---

## 2. Open Knowledge Format (OKF v0.2) & Cognitive Graph Ranking

### OKF v0.2 Frontmatter Schema

```yaml
---
title: "Project Alpha Kickoff"
description: "High-throughput telemetry ingestion pipeline using SQLite WAL."
created: "2026-09-17T12:00:00"
updated: "2026-09-17T14:30:00"
type: project-note
status: active
tags:
  - project
  - alpha
generated:
  by: abby/agent:steward
  at: "2026-09-17T12:00:00Z"
verified:
  - by: human:bookian
    at: "2026-09-17T14:30:00Z"
stale_after: "2027-09-17T00:00:00Z"
sources:
  - resource: "https://example.com/spec"
    title: "Upstream RFC"
---
```

### Trust Multipliers & Cognitive Centrality Formula
Search relevance combines SQLite FTS5 BM25 ranking (`notes_fts`) with four multiplicative signals:
1. **Domain Weight**: `03 - Resources/` ($1.20\times$), `01 - Projects/` & `02 - Areas/` ($1.00\times$), `00 - Inbox/` ($0.80\times$), `04 - Archives/` ($0.35\times$).
2. **OKF Trust Tier**:
   - `human-reviewed` ($1.25\times$): Verified by human owner (`human:<id>`). Highest epistemic authority.
   - `machine-confirmed` ($1.00\times$): Synthesized or verified by AI agents (`abby/agent:*`, `agent:<id>`).
   - `unverified` ($0.90\times$): Newly captured raw notes without verification attestations.
3. **Temporal Freshness**: Notes past their `stale_after` timestamp receive a $0.60\times$ penalty (or are excluded via `--fresh-only`).
4. **Cognitive Graph Centrality**: Active inbound backlinks dynamically boost concept hubs and Maps of Content (MOCs):
   $$\text{Boost} = 1.0 + 0.15 \times \log_2(1 + \min(\text{active\_backlinks}, 31)) \quad (\text{capped at } 1.75\times)$$

---

## 3. CLI & Test Runner Reference

### Installation & Quick Start

```bash
# Add CLI wrapper to PATH or execute directly from .system/abby/bin/
export PATH="$PWD/.system/abby/bin:$PATH"

# 1. Audit vault health and runtime diagnostics
abby check
abby doctor
abby info

# 2. Capture a note into 00 - Inbox/
abby new "Quick Note" --body "Initial capture." --description "Concise 15-35 word summary."

# 3. Relocate, verify, or archive notes (supports --dry-run preview)
abby move "00 - Inbox/Quick Note.md" "resources/Systems" --description "Concise 15-35 word summary."
abby verify "03 - Resources/Systems/Quick Note.md" --by human:bookian
abby archive "01 - Projects/Completed Project.md" --dry-run

# 4. Cognitive search with trust, freshness, and highlighted snippets
abby find "consensus" --trust human-reviewed --fresh-only --snippets
abby find "architecture" --domain resources --json

# 5. Link graph inspection & atomic vault-wide refactoring
abby links "03 - Resources/Consensus.md" --depth 2
abby links --broken --headings
abby links --orphans
abby links refactor "03 - Resources/Old Title.md" "New Title" --dry-run

# 6. OKF v0.2 schema linting and auto-remediation
abby lint --strict
abby lint --domain projects --fix --dry-run --strict

# 7. SQLite FTS5 cache lifecycle
abby cache status
abby cache rebuild
abby cache prune
```

### Parallel Architecture & Test Runner (`abby-test`)

```bash
# Instant AST architecture gate (< 3s: enforces < 500 LOC target, CC <= 20, 0 deferred imports)
.system/abby/bin/abby-test arch

# Full parallel regression suite across 8 workers (< 20s)
.system/abby/bin/abby-test all

# Targeted file or keyword execution with fail-fast (-x)
.system/abby/bin/abby-test test_transaction -x
.system/abby/bin/abby-test -k doctor
```

---

## 4. Model Context Protocol (MCP) Reference (`.system/abby/bin/abby-mcp`)

Abby exposes **12 deterministic tools** over JSON-RPC 2.0 stdio with 1:1 service parity with the CLI:

| Tool | Signature & Purpose |
| :--- | :--- |
| `vault_check` | `vault_check()` — Read-only audit of PARA+ directory structure. |
| `vault_init` | `vault_init()` — Idempotently scaffold missing PARA+ directories and starter templates. |
| `note_capture` | `note_capture(title, body?, description?, tags?, generated?, verified?, sources?)` — Stage note in `00 - Inbox/`. |
| `domain_list` | `domain_list(domain="inbox"\|"projects"\|"areas"\|"resources"\|"archives")` — Chronological FIFO domain queue. |
| `note_read` | `note_read(note)` — Retrieve structured payload (`path`, `title`, `frontmatter`, `body`, `content`) in `00`–`04`. |
| `note_move` | `note_move(note, target, description?, dry_run?)` — Relocate note to `01`–`03` with automatic OKF `type`/`status` alignment. |
| `note_archive` | `note_archive(note, dry_run?)` — Retire note into `04 - Archives/` (`status: archived`). |
| `note_verify` | `note_verify(note_path, actor?, dry_run?)` (alias `note`) — Record verification attestation (`human:<id>` or `abby/agent:<role>`). |
| `note_refactor` | `note_refactor(source, target, links_only?, dry_run?)` — Transactional rename and vault-wide link rewriting (`FileSystemTransaction`). |
| `vault_search` | `vault_search(query?, domain?, status?, type?, tags?, limit?, snippets?, trust_tier?, fresh_only?, json?)` — Cognitive BM25 search. |
| `vault_links` | `vault_links(note?, mode="outbound"\|"backlinks"\|"broken"\|"orphans"\|"unreferenced", depth=1..3, headings?, domain?)` — Graph inspection. |
| `vault_lint` | `vault_lint(note?, domain?, fix?, dry_run?, strict?)` — OKF v0.2 schema validation and non-destructive auto-repair. |

---

## 5. Client Configuration

### Google Antigravity / Jetski
```json
{
  "mcpServers": {
    "abby": {
      "command": "/bin/bash",
      "args": ["-c", "cd /path/to/vault && .system/abby/bin/abby-mcp"],
      "env": { "ABBY_VAULT_ROOT": "/path/to/vault" }
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`) & Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "abby": {
      "command": ".system/abby/bin/abby-mcp"
    }
  }
}
```

---

## 6. Authoritative Documentation & Playbooks

- **Always-On Agent Rules**: [`AGENTS.md`](AGENTS.md)
- **Editorial & Tagging Style Standard**: [`STYLE.md`](STYLE.md)
- **Consolidated Skills**: [`.agents/skills/vault-synthesize/SKILL.md`](.agents/skills/vault-synthesize/SKILL.md), [`.agents/skills/vault-curate/SKILL.md`](.agents/skills/vault-curate/SKILL.md), [`.agents/skills/vault-technician/SKILL.md`](.agents/skills/vault-technician/SKILL.md)
- **Subagent Personas**: [`.agents/subagents/steward.md`](.agents/subagents/steward.md), [`.agents/subagents/technician.md`](.agents/subagents/technician.md)
- **System Design & Normative Specification**: [`.system/specs/DESIGN.md`](.system/specs/DESIGN.md), [`.system/specs/SPECIFICATION.md`](.system/specs/SPECIFICATION.md)
