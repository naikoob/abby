---
name: "vault-curate"
description: "Automated vault health audits, broken link and heading anchor diagnostics, transactional note refactoring, strict OKF schema linting/fixing, and project archival."
---

# Vault Curation Playbook

This playbook is the single source of truth for auditing structural health, validating the Wikilink and `#Heading` anchor graph, performing transactional vault-wide renames, enforcing strict OKF v0.2 schema compliance, and retiring completed projects.

## Linked Editorial & Workflow Standards

- **[`STYLE.md`](../../../STYLE.md)**: Authoritative reference for flat kebab-case tags, 15–35 word active-voice `description` summaries, and max `###` heading depth when remediating lint defects.
- **[`vault-synthesize/SKILL.md`](../vault-synthesize/SKILL.md)**: Execute **Path B (Atomic Decomposition)** before archiving any completed `01 - Projects/` initiative containing reusable architectures or decision records.

## User Input

```text
$ARGUMENTS
```

Optional arguments:
- `domain`: Target domain to audit or repair (`inbox`, `projects`, `areas`, `resources`, `archives`).
- `fix`: Apply automatic schema repairs (default: `false`).
- `dry_run`: Preview changes without mutating disk (default: `true`).

---

## Workflow Steps

### 1. Structural Directory Audit
- Verify all required PARA+ directories exist:
  - MCP: `vault_check()` | CLI: `abby check`
- If missing directories are reported, scaffold them idempotently via `vault_init()` (`abby init`).

### 2. Link Graph & Heading Anchor Diagnostics
- Audit broken Wikilinks and invalid `#Heading` section anchors:
  - MCP: `vault_links(mode="broken", headings=True)` | CLI: `abby links --broken --headings`
- Identify isolated orphan notes (0 inbound and 0 outbound links):
  - MCP: `vault_links(mode="orphans")` | CLI: `abby links --orphans`
- Inspect multi-hop concept neighborhoods (`depth: 1..3`):
  - MCP: `vault_links(note="<note>", depth=2)` | CLI: `abby links "<note>" --depth 2`

### 3. Transactional Note Refactoring (`dry_run` First)
- Rename notes and atomically rewrite all inbound Wikilinks across the vault (protected by `FileSystemTransaction` two-phase LIFO rollback):
  1. **Preview**: `note_refactor(source="<old>", target="<new>", links_only=False, dry_run=True)`
  2. **Execute**: `note_refactor(source="<old>", target="<new>", links_only=False, dry_run=False)`
  - CLI equivalent: `abby links refactor "<old>" "<new>" [--dry-run] [--links-only]`

### 4. Strict OKF Schema Linting & Auto-Fix
- Audit schema compliance and `01`–`03` executive description presence (`strict=True`):
  - MCP: `vault_lint(domain="<domain>", strict=True)` | CLI: `abby lint --domain <domain> --strict`
- Preview non-destructive repairs before applying:
  1. **Preview**: `vault_lint(domain="<domain>", fix=True, dry_run=True, strict=True)`
  2. **Execute**: `vault_lint(domain="<domain>", fix=True, dry_run=False, strict=True)`
- If a note in `01`–`03` fails strict linting due to a missing `description`, inspect it via `note_read(note="<note>")` and inject a 15–35 word active-voice summary per [`STYLE.md`](../../../STYLE.md) using `note_move` to its current domain.
- *Exclusion Note*: Root Markdown files (`/AGENTS.md`, `/STYLE.md`, `/README.md`, `/DESIGN.md`, `/SPECIFICATION.md`) and `05 - Assets/Templates/` are outside `00`–`04` and excluded from schema linting.

### 5. Pre-Archive Distillation & Project Retirement
- Before retiring a completed project in `01 - Projects/`:
  1. Inspect project notes via `note_read` and distill reusable architectures or ADRs into `03 - Resources/` following [`vault-synthesize/SKILL.md`](../vault-synthesize/SKILL.md) (Path B).
  2. Retire the project note to `04 - Archives/`:
     - MCP: `note_archive(note="<note>", dry_run=False)` | CLI: `abby archive "<note>"`

### 6. Structured Curation Report
Return this summary to the caller:

```markdown
### Vault Curation Report
- **Structural Status**: Healthy (6/6 PARA+ domains verified)
- **Schema Audit (`strict=True`)**: <total> scanned, <clean> clean, <fixed> repaired
- **Link & Anchor Graph**: <broken_resolved> broken links fixed, <orphans> orphans flagged
- **Projects Distilled & Retired**: <list or None>
```
