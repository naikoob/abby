# Abby System Package (`abby`)

This package contains the core Python engine, CLI utilities, SQLite FTS5 search indexer, and MCP server for the Abby Knowledge Vault.

---

## Architecture & Boundaries

- **Pure Standard Library**: Zero external pip dependencies.
- **Atomic File Mutations & Crash Safety**: All note writes, moves, archives, verifications, refactoring, and auto-lint repairs route through `atomic_write_text` in `abby.utils.io`. Writes occur to temporary sibling files before atomic replacement via `os.replace`, guaranteeing crash resilience and preventing file truncation.
- **Two-Phase Rollback & `FileSystemTransaction` LIFO Context Manager**: Vault refactoring (`refactor_note`) and complex multi-file mutations operate under a unified transactional rollback boundary (`FileSystemTransaction` in `abby.utils.transaction`). If any stage fails during staging, renaming, or link rewriting, all completed filesystem mutations roll back in strict LIFO order, ensuring atomic consistency without partial writes.
- **Cache Schema Busting (`CACHE_SCHEMA_VERSION`)**: SQLite cache compatibility is enforced via an integer `CACHE_SCHEMA_VERSION` (in `abby.core.cache`). If SQLite metadata or table migrations differ from the runtime version, the cache engine automatically invalidates and rebuilds the SQLite schema and FTS5 indices without manual user intervention.
- **Structural Subtyping via `typing.Protocol`**: Decoupled subsystem boundaries utilize formal protocols (`abby.models.protocols`) rather than rigid concrete inheritance, defining explicit interfaces for filesystem undo operations (`FileSystemUndo`), cache synchronization (`CacheSyncer`), and note target resolution (`NoteTargetResolver`).
- **Cyclomatic Complexity Gatekeeping**: Every function in `src/abby/` is strictly bounded to $CC \le 20$, with modularized pipeline stages (frontmatter remediation, search query generation, tokenization) achieving $CC \le 15$ (enforced by AST tests in `tests/integration/test_architecture.py`).
- **750 LOC Boundary & 500 LOC Target**: Every Python file in `src/abby/` is strictly constrained to $< 750$ lines of code, with all modules maintained strictly $< 500$ LOC and majority $< 200$ LOC (enforced by `tests/integration/test_architecture.py`).
- **Zero Circular Dependencies & Zero Deferred Imports**: Isolated module import tests and AST checks enforce explicit, top-level imports without hidden execution-time cycles.
- **Zero Dynamic `__getattr__` Shims**: All modules use explicit, statically analyzable exports without PEP 562 dynamic resolution fallbacks.
- **Air-Gap Persona Model**: The system domain operates strictly outside `00`–`05`. System utilities never mutate human thought or note formatting arbitrarily.
- **Strict Layering**:
  - `models` and `utils`: Foundational layer. Must never depend on `core`, `services`, `cli`, or `mcp`.
  - `core` and `services`: Domain logic layer. Must never import presentation layers (`cli`, `mcp`).
  - `cli` and `mcp`: Presentation layer. Consumes domain logic, models, and utilities.

---

## Package Layout

```text
.system/abby/
├── pyproject.toml        # Pure stdlib build definition
├── bin/
│   ├── abby              # CLI wrapper entrypoint
│   ├── abby-mcp          # MCP server entrypoint
│   └── abby-test         # High-velocity parallel test runner (< 20s)
├── src/abby/
│   ├── constants.py      # Vault directory names, domain mappings, regexes
│   ├── utils/
│   │   ├── io.py         # Stream output and error logging
│   │   ├── templates.py  # Note template scaffolds
│   │   ├── time.py       # ISO-8601 parsing, UTC generation, staleness checks
│   │   ├── transaction.py# FileSystemTransaction LIFO rollback context manager (< 90 LOC)
│   │   └── yaml.py       # Pure YAML scalar/mapping parsing, escaping, and comment stripping
│   ├── models/
│   │   ├── okf.py        # OKF dataclasses (OKFFrontmatter, ParsedFrontmatter, InboxNote)
│   │   ├── trust.py      # TrustTier, VerificationEvent, ProvenanceSource, canonical actor parsing
│   │   ├── search.py     # SearchFilter and SearchMatchItem models
│   │   ├── links.py      # NoteLinkRecord, BacklinkOccurrence, RefactorResult
│   │   ├── lint.py       # Lint violation and report models
│   │   ├── protocols.py  # Structural subtyping protocols (FileSystemUndo, CacheSyncer, NoteTargetResolver)
│   │   └── exceptions.py # Domain exception hierarchy
│   ├── services/
│   │   ├── okf_parser.py     # Dedicated OKF frontmatter parsing and tokenization (< 320 LOC)
│   │   ├── okf_serializer.py # Dedicated OKF serialization and non-destructive mutation (< 220 LOC)
│   │   └── lint/             # OKF schema validation, rules, scanner, and remediation
│   │       ├── rules.py      # Lint validation rules and structural constraints
│   │       ├── validators.py # Field-level schema validators
│   │       ├── trust_validators.py # Actor syntax and provenance validation
│   │       ├── scanner.py    # Frontmatter tokenization integration
│   │       ├── remediation.py# Non-destructive automated fix engine
│   │       └── reporting.py  # Human-readable and JSON lint report formatters
│   ├── core/
│   │   ├── domain.py         # Centralized DomainService and canonicalization authority (< 100 LOC)
│   │   ├── discovery.py      # Vault root discovery and filesystem note scanning (< 110 LOC)
│   │   ├── cache.py          # SQLite WAL cache and schema migrations (< 380 LOC)
│   │   ├── scoring.py        # Cognitive ranking formula & multiplier computation (< 100 LOC)
│   │   ├── search.py         # BM25 full-text search with cognitive and faceted filtering (< 180 LOC)
│   │   ├── search_builder.py # SQL query generation, regex highlighting, snippet extraction (< 340 LOC)
│   │   ├── resolution.py     # Ambiguity detection and candidate path resolution (< 190 LOC)
│   │   ├── verify.py         # Note verification service & frontmatter mutation (< 130 LOC)
│   │   ├── lifecycle.py      # Note move, archive, and collision resolution (< 270 LOC)
│   │   ├── intake.py         # Fast note intake and filename sanitization (< 130 LOC)
│   │   ├── health.py         # Vault health inspection (< 70 LOC)
│   │   ├── doctor.py         # Diagnostic suite for environment, cache, and assets (< 140 LOC)
│   │   ├── init.py           # Idempotent directory and asset scaffolding (< 140 LOC)
│   │   └── graph/            # Knowledge graph engine (parser, cache, diagnostics, traversal, refactor)
│   │       ├── parser.py     # Wikilink parsing and heading anchor extraction (< 140 LOC)
│   │       ├── cache.py      # Link resolution and active backlink materialization (< 130 LOC)
│   │       ├── diagnostics.py# Broken link, orphan, and unreferenced note detection (< 330 LOC)
│   │       ├── traversal.py  # Multi-hop outbound and inbound backlink queries (< 170 LOC)
│   │       └── refactor.py   # Atomic note renames, link rewrites, and rollback safety (< 290 LOC)
│   ├── cli/
│   │   ├── handlers.py       # CLI dispatch routing and command orchestration (< 260 LOC)
│   │   ├── parser.py         # Root argument parser assembly (< 90 LOC)
│   │   ├── args/             # Modular argparse subcommand definitions (< 210 LOC)
│   │   │   ├── vault.py      # check, init, info, doctor, cache argument parsers
│   │   │   ├── lifecycle.py  # new, list, move, archive, verify argument parsers
│   │   │   ├── search_graph.py # find, links argument parsers
│   │   │   └── lint_mcp.py   # lint, mcp argument parsers
│   │   └── commands/         # Modular CLI presentation and formatting (< 330 LOC)
│   │       ├── vault.py      # execute_check, execute_init, execute_info, execute_doctor, execute_cache
│   │       ├── notes.py      # execute_new, execute_list, execute_move, execute_archive, execute_verify
│   │       ├── search.py     # execute_find
│   │       ├── links.py      # execute_links, execute_broken, execute_orphans, execute_refactor
│   │       └── lint.py       # execute_lint
│   └── mcp/
│       ├── types.py          # MCP Content and Tool Call Result dataclasses (< 90 LOC)
│       ├── schemas.py        # JSON schemas for all 12 MCP tools (< 330 LOC)
│       ├── registry.py       # ToolRegistry dispatch abstraction (< 70 LOC)
│       ├── tools.py          # Facade exporting execute_tool and tool definitions (< 140 LOC)
│       ├── server.py         # JSON-RPC 2.0 stdio server (< 190 LOC)
│       ├── protocol.py       # JSON-RPC framing and protocol serialization (< 160 LOC)
│       └── handlers/         # Modular MCP tool execution handlers (< 200 LOC)
│           ├── vault.py      # handle_vault_check, handle_vault_init
│           ├── notes.py      # handle_note_capture, handle_domain_list, handle_note_read, handle_note_move, handle_note_archive, handle_note_verify
│           ├── search.py     # handle_vault_search
│           ├── graph.py      # handle_vault_links, handle_note_refactor
│           └── lint.py       # handle_vault_lint
└── tests/
    ├── unit/                 # Tier 1 in-memory logic tests
    └── integration/          # Tier 2 & 3 sandboxed filesystem and CLI/MCP tests (65 test files across 8 parallel workers)
```

---

## Testing & Type Verification

Run the high-velocity parallel test suite, targeted unit tests, or static quality gates via the dedicated runner wrapper:

```bash
# Run all test suites in parallel (< 20s across 8 workers)
.system/abby/bin/abby-test all

# Instant AST architecture gate (< 3s for cyclomatic complexity and LOC checks)
.system/abby/bin/abby-test arch

# Targeted execution of a single test file or path
.system/abby/bin/abby-test test_transaction
.system/abby/bin/abby-test tests/unit/test_scoring.py

# Filter test files by keyword pattern
.system/abby/bin/abby-test -k doctor

# Stop immediately upon first test failure (fail-fast)
.system/abby/bin/abby-test -x

# Run unit tests only (< 3s)
.system/abby/bin/abby-test unit

# Run integration tests only
.system/abby/bin/abby-test integration

# Run static type checking gate (mypy/pyright detection with stdlib fallback)
.system/abby/bin/abby-test typecheck

# Run static type checking in strict CI gatekeeping mode
.system/abby/bin/abby-test typecheck --strict

# Sequential execution fallback
.system/abby/bin/abby-test --sequential
```

### Static Quality Gates (Mypy & Ruff)

When developing or extending system components, verify code quality and style using standard quality gates:

```bash
# Static type checking via mypy
python3 -m mypy src/abby

# Fast linting and format checks via ruff (if installed)
ruff check src/abby
ruff format --check src/abby
```

