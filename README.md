# CORA

**Continuously Overpromised, Rarely Automated** — a unified operations platform for large-scale research facilities. Pilot: APS beamline 2-BM at Argonne National Laboratory. Long-horizon goal: facility-neutral across photon sources, neutron sources, free-electron lasers, and HPC centres.

## Status

**Phase 0 — project skeleton.** No domain logic yet. Walking-skeleton wiring being added in subsequent phases.

## Quick start

Requires: Python 3.13.12 (managed via uv), Docker (for Postgres), [Atlas](https://atlasgo.io/) (for schema migrations). Node 24 LTS comes later for the frontend.

```bash
# Install Atlas (one-time per machine)
curl -sSf https://atlasgo.sh | sh

# Install Python deps via uv
make install            # runs `uv sync` inside apps/api

# Install pre-commit hooks (one-time per clone)
make precommit

# Start Postgres + pgvector
make db-up

# Apply schema migrations
make migrate-apply

# Run smoke tests
make test

# Start the dev server
make dev
# API at http://localhost:8000
# Health check at http://localhost:8000/health
# REST API: POST /actors  (see /docs for OpenAPI)
# MCP server mounted at /mcp (streamable HTTP transport)
```

Run `make help` for the full list of dev commands.

See [CONTRIBUTING.md](CONTRIBUTING.md) for commit message conventions and BC layout.

## API surfaces

CORA exposes every command on two equivalent surfaces backed by the same handler:

**REST.** OpenAPI docs at `http://localhost:8000/docs` (Swagger UI) and `/redoc`. Example:

```bash
curl -X POST http://localhost:8000/actors \
  -H 'Content-Type: application/json' \
  -d '{"name": "Doga"}'
# -> 201 {"actor_id": "01900000-..."}
```

**MCP** (Model Context Protocol — for LLM agents). Streamable HTTP transport mounted at `/mcp`. The full handshake is `initialize` → `notifications/initialized` → `tools/call`. Example using a JSON-RPC client:

```bash
# 1. Initialize, capture mcp-session-id from response headers
curl -i -X POST http://localhost:8000/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
       "params":{"protocolVersion":"2025-06-18","capabilities":{},
                 "clientInfo":{"name":"cli","version":"0.1"}}}'

# 2. Send notifications/initialized + 3. Call the tool  (use the captured session id)
# Response is structured content with the new actor_id.
```

For Claude Code or other MCP-aware clients, point the client at `http://localhost:8000/mcp` and the `register_actor` tool appears alongside any future tools.

## Repo layout (monorepo)

```
cora/
├── apps/                      # deployable units
│   ├── api/                   # FastAPI + MCP backend (Python)
│   │   ├── src/cora/
│   │   │   ├── api/           # HTTP + MCP entrypoints
│   │   │   ├── shared/        # cross-BC primitives (added on demand)
│   │   │   └── <bc>/          # bounded contexts (Equipment scaffolded; others on demand)
│   │   │       ├── domain/         # pure functional core: deciders, value objects, aggregates
│   │   │       ├── application/    # commands, queries, integration events
│   │   │       └── infrastructure/ # asyncpg adapters, port implementations
│   │   ├── tests/
│   │   │   ├── unit/          # pure, no I/O
│   │   │   ├── integration/   # require Postgres or other external services
│   │   │   ├── contract/      # REST/MCP schema verification
│   │   │   └── e2e/           # full end-to-end
│   │   └── pyproject.toml
│   ├── web/                   # Next.js frontend (Phase 0.5+)
│   └── workers/               # background processors / agents (later)
├── packages/                  # shared libraries (created on demand)
│   ├── contracts/             # OpenAPI/MCP schemas + generated TS types (later)
│   └── ui/                    # shared frontend components (later)
├── infra/                     # local dev infra + IaC
│   └── docker-compose.yml
├── docs/                      # design docs (placeholder)
├── Makefile                   # top-level orchestration
├── .python-version            # repo-wide Python pin
└── README.md
```

Test layout is **separate `tests/` mirroring `src/`** with pytest's `--import-mode=importlib`, per current Python community best practice for `src/` layouts.

## Architecture (high level)

Modern functional DDD with bounded contexts. Hexagonal (Functional Core / Imperative Shell). Postgres event sourcing (asyncpg, hand-rolled). REST + MCP API surface. Recipe ladder (Method → Practice → Plan → Run) is the facility-neutrality mechanism.

Modeling lenses adopted: ISA-95 (structural), ISA-88 (Track A: episodic procedures), ISA-106 (Track B: continuous operations), ISA-99 (Track C: trust topology), ISO/IEC 42001 + NIST AI RMF (AI governance), W3C PROV-O (provenance vocabulary at API boundaries).

## Tooling

- **uv** — Python package management
- **ruff** — lint + format (Python)
- **pyright** — type checking (strict mode)
- **pytest + pytest-asyncio** — testing
- **Biome** — lint + format (JS/TS, frontend later)
