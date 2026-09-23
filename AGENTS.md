# Abby Knowledge Vault: Agent Operating Guide & Protocol

## 1. Operating Tenets, The Air-Gap Persona Model & Dispatch Matrix

- **Knowledge Domain (`00 - Inbox/`, `01 - Projects/`, `02 - Areas/`, `03 - Resources/`, `04 - Archives/`, `05 - Assets/`)**: Mutate **strictly** via Abby's 12 MCP tools or `.system/abby/bin/abby` CLI—never via raw `write_to_file` or `replace_file_content` inside `00`–`04`. Preserve human prose, custom YAML properties, and Obsidian `^blockid` anchors.
- **System Domain (`.system/`, `.agents/`, `AGENTS.md`, `STYLE.md`, `README.md`)**: Zero live note mutations in `00`–`05` (use `tempfile.TemporaryDirectory` for engine tests). `.obsidian/` is off-limits unless explicitly tasked.

| Intent / Request | Executor | Playbook / Interface | Threshold & Verification Gate |
| :--- | :--- | :--- | :--- |
| **Vault Q&A, status, research** | **Root Agent** | `vault_search(snippets=True, fresh_only=True)` $\rightarrow$ `vault_links` $\rightarrow$ `note_read` | **Built-in Fast Path** (§2). Cite every vault claim with `[[Note Title#Anchor\|alias]]`. |
| **Single-note capture** | **Root Agent** | `note_capture(title, body, description, tags, sources)` (`abby new`) | **Built-in Fast Path**. Follow with `note_move` if placing directly into `01`–`03`. |
| **Inbox triage, PARA routing, concept synthesis, pre-archive distillation** | **Root** ($\le 2$ notes) / **Steward** ($\ge 3$ notes or brain dump) | [`.agents/skills/vault-synthesize/SKILL.md`](.agents/skills/vault-synthesize/SKILL.md) / [`.agents/subagents/steward.md`](.agents/subagents/steward.md) | **Gate**: `vault_lint(strict=True)` + `vault_links(mode="broken", headings=True)`. **Never** run `abby-test`. |
| **Health audit, broken links, rename refactor, strict lint, archival** | **Root** (1 note) / **Steward** (vault-wide) | [`.agents/skills/vault-curate/SKILL.md`](.agents/skills/vault-curate/SKILL.md) / [`.agents/subagents/steward.md`](.agents/subagents/steward.md) | Preview mutations with `dry_run=True` first. Distill `01 - Projects/` into `03` before `note_archive`. |
| **Engine code, FTS5 cache, MCP schemas, tests, specs** | **Technician** | [`.agents/skills/vault-technician/SKILL.md`](.agents/skills/vault-technician/SKILL.md) / [`.agents/subagents/technician.md`](.agents/subagents/technician.md) | **Gate**: `abby-test arch` ($<3\text{s}$) + `abby-test all` ($<20\text{s}$) + `git status` (0 edits in `00`–`05`). |

## 2. Knowledge Grounding & Retrieval Protocol

1. **Search First**: Always query `vault_search(query="...", snippets=True, fresh_only=True)` (`abby find "..." --snippets --fresh-only`) prior to answering vault questions. Answer directly from snippets and `description` when sufficient.
2. **Honesty Gate**: If 0 records match, state verbatim: *"I searched the vault for `<query>`, but found no matching records."* Never hallucinate from base model weights.
3. **Epistemic & Graph Priority**: Prefer `[human-reviewed]` $>$ `[machine-confirmed]` $>$ `[unverified]` (exclude `[stale]`). For multi-hop synthesis, start at the highest-`active_backlinks` hub or `[[<Topic> MOC]]` and expand via `vault_links(note="...", depth=1..3)` + `note_read(note="...")`.

## 3. Authoring, Mesh & Handover Contracts ([`STYLE.md`](STYLE.md))

- **OKF v0.2 Metadata**: Notes in `01`–`03` require a **15–35 word active-voice `description`** (zero *"This note covers..."* filler), flat kebab-case `tags` (no `#` prefix), and max `###` (H3) heading depth per [`STYLE.md`](STYLE.md) and [`05 - Assets/Templates/`](05%20-%20Assets/Templates).
- **Bidirectional Graph Mesh**: Every atomic note in `03 - Resources/` must receive $\ge 1$ inbound Wikilink from an existing hub or `[[<Topic> MOC]]` (scaffold a `[[<Topic> MOC]]` when a cluster reaches $\ge 5$ notes).
- **Handover Breadcrumb**: When pausing or finishing work on an active `01 - Projects/` or `02 - Areas/` note, append `## Handover Summary` (`Updated`, `Actor`, `Current Progress`, `Open Questions`, `Next Actions`).

## 4. CLI Fallback Cheat Sheet (Full Reference in [`README.md`](README.md))

- **Vault & Note Lifecycle**: `.system/abby/bin/abby [check | doctor | init | info | list <domain> | new <title> --body <b> --description <d> | move <src> <dst> --description <d> --dry-run | archive <note> --dry-run | verify <note> --by <actor>]`
- **Search, Graph, Lint & Cache**: `.system/abby/bin/abby [find <q> --snippets --fresh-only --trust <tier> | links <note> --broken --headings --orphans --depth <1..3> | links refactor <src> <dst> --dry-run | lint --strict --fix --dry-run | cache status|rebuild|prune]`
