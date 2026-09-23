---
name: "vault-technician"
description: "System Domain maintenance playbook for Python engine code, SQLite FTS5 cache management, MCP schema parity, AST architecture gates, parallel test execution, and zero-note-mutation verification."
---

# Vault Technician Playbook

This playbook is the single source of truth for maintaining `.system/abby/`, managing the SQLite FTS5 search cache, verifying MCP server protocol schemas, and running the multi-tier regression suite while enforcing the Constitutional Air-Gap.

## Operating Boundary & Constitutional Guardrails

> [!CAUTION]
> **AIR-GAP GUARDRAIL ([`.system/specs/SPECIFICATION.md`](../../../.system/specs/SPECIFICATION.md))**:
> - Operate **strictly within the System Domain** (`.system/`, `.agents/`, `AGENTS.md`, `README.md`, tests).
> - **NEVER** create, modify, rename, or delete notes in the Knowledge Domain (`00 - Inbox/` through `05 - Assets/`), except when explicitly syncing starter template skeletons in `05 - Assets/Templates/` with [`.system/abby/src/abby/utils/templates.py`](../../../.system/abby/src/abby/utils/templates.py).
> - All filesystem tests MUST execute inside disposable `tempfile.TemporaryDirectory` fixtures.

## User Input

```text
$ARGUMENTS
```

Optional arguments:
- `rebuild_cache`: Force a full SQLite FTS5 rebuild (default: `false`).
- `test_scope`: Test tier or file target (`arch`, `all`, `unit`, `integration`, or `<test_file>`; default: `all`).

---

## Workflow Steps

### 1. Engine & Environment Diagnostics
- Run holistic environment, template, and SQLite health checks:
  ```bash
  .system/abby/bin/abby doctor
  .system/abby/bin/abby info
  ```
- Maintain pure Python 3.10+ stdlib layering (`models`/`utils` $\rightarrow$ `core`/`services` $\rightarrow$ `cli`/`mcp`) with zero third-party pip dependencies.
- When updating root `AGENTS.md`, `STYLE.md`, or `05 - Assets/Templates/*.md`, keep fallback constants in [`.system/abby/src/abby/utils/templates.py`](../../../.system/abby/src/abby/utils/templates.py) (`FALLBACK_AGENTS_CONTENT`, `FALLBACK_STYLE_CONTENT`, `FALLBACK_TEMPLATES`) synchronized.

### 2. SQLite FTS5 Cache Lifecycle
- Inspect or rebuild `.system/cache/vault.db` (governed by `CACHE_SCHEMA_VERSION`):
  ```bash
  .system/abby/bin/abby cache status
  .system/abby/bin/abby cache rebuild
  .system/abby/bin/abby cache prune
  ```

### 3. MCP Server Verification
- Verify the 12 JSON-RPC 2.0 stdio tools in [`.system/abby/src/abby/mcp/schemas.py`](../../../.system/abby/src/abby/mcp/schemas.py):
  ```bash
  test -x .system/abby/bin/abby-mcp
  .system/abby/bin/abby-mcp --help
  ```

### 4. Two-Stage Test & Architecture Gate (Mandatory Before Completion)
1. **Stage 1 — Instant AST Architecture Gate ($< 3\text{s}$)**:
   Enforces module $< 500$ LOC target ($< 750$ hard limit), cyclomatic complexity $CC \le 20$, zero deferred imports, and zero circular dependencies:
   ```bash
   .system/abby/bin/abby-test arch
   ```
2. **Stage 2 — Parallel Test Suite ($< 20\text{s}$ across 8 workers)**:
   ```bash
   .system/abby/bin/abby-test all
   # Or targeted execution during iteration:
   .system/abby/bin/abby-test <test_file> -x
   ```

### 5. Air-Gap Verification & Report
- Assert zero unintended modifications in `00`–`05`:
  ```bash
  git status --porcelain
  ```
- Return this technical report to the caller:

```markdown
### Vault Technician Report
- **Subsystems Modified**: <paths>
- **AST Architecture Gate (`abby-test arch`)**: PASSED (<LOC / CC check>)
- **Regression Suite (`abby-test all`)**: <count> tests passed (100% OK)
- **Cache Status**: <Synced / Rebuilt>
- **Air-Gap Check (`00`–`05`)**: PASSED (0 knowledge notes modified)
```
