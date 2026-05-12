# CORA

[![CI](https://github.com/xmap/cora/actions/workflows/ci.yml/badge.svg)](https://github.com/xmap/cora/actions/workflows/ci.yml)
[![Docs](https://github.com/xmap/cora/actions/workflows/docs.yml/badge.svg)](https://xmap.github.io/cora/)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)

A unified operations platform for large-scale research facilities. Pilot: APS beamline 2-BM at Argonne National Laboratory. Long-horizon goal: facility-neutral across photon sources, neutron sources, free-electron lasers, and HPC centres.

The name is also the diagnosis: **Continuously Overpromised, Rarely Automated**. Most facility software lives forever as a slide-deck capability. CORA is the version that ships.

## Status

**Active development; pre-1.0.** Foundation infrastructure (event store, ports, BC scaffolding) and several bounded-context keystones are in place. APIs, schema, and BC topology are still subject to change. Not yet production-ready.

## Documentation map

CORA's docs are layered so a reader can stop at the level they need. The full set is rendered as a static site at **[xmap.github.io/cora](https://xmap.github.io/cora/)** (auto-deployed on every push to `main`).

| Layer | Vocabulary | Where |
| --- | --- | --- |
| 1. Capability | What CORA does for users | this README |
| 2. Architecture | Roles and patterns, no products | [docs/architecture.md](docs/architecture.md) |
| 3. Implementation | Current product picks and reasoning | [docs/stack.md](docs/stack.md), [CONTRIBUTING.md](CONTRIBUTING.md) |
| 4. Pinned versions | Exact strings | `apps/api/pyproject.toml`, `Makefile`, `infra/atlas/migrations/` |

Vocabulary in any layer is defined in [docs/glossary.md](docs/glossary.md).

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

**MCP** (Model Context Protocol, the agent surface). Streamable HTTP transport mounted at `/mcp`. The full handshake is `initialize` → `notifications/initialized` → `tools/call`. Example using a JSON-RPC client:

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

For Claude Code or other MCP-aware clients, point the client at `http://localhost:8000/mcp`; tools across every scaffolded BC (`access`, `equipment`, `recipe`, `run`, `data`, `decision`, `subject`, `trust`) appear in the client.

## Repo layout (monorepo)

```
cora/
├── apps/
│   └── api/                # backend
│       ├── src/cora/
│       │   ├── api/        # entrypoints
│       │   ├── infrastructure/  # ports, kernel, adapters
│       │   └── <bc>/       # one folder per bounded context
│       │       ├── aggregates/  # state, events, evolver
│       │       └── features/    # vertical slices
│       ├── tests/          # unit, integration, contract, architecture
│       └── pyproject.toml
├── infra/
│   ├── atlas/              # migrations
│   └── docker-compose.yml
├── docs/                   # architecture, stack, glossary
├── CONTRIBUTING.md
├── Makefile
└── README.md
```

- **`<bc>/`** is one of 8 bounded contexts scaffolded today: `access`, `equipment`, `recipe`, `run`, `data`, `decision`, `subject`, `trust`. Each follows the same `aggregates/` + `features/` shape (see [CONTRIBUTING.md](CONTRIBUTING.md)).
- **`tests/`** mirrors `src/` and splits by category: `unit/` (pure), `integration/` (real Postgres), `contract/` (REST and MCP schema), `architecture/` (fitness checks).
- **Planned but not yet on disk:** `apps/web` (frontend), `apps/workers` (background processors and agents), `packages/` (shared libs).

## Architecture (high level)

Functional DDD with bounded contexts. Hexagonal (Functional Core / Imperative Shell). Event-sourced backend on a relational store. Two equivalent API surfaces (REST and an agent protocol) backed by the same handler. The recipe ladder (Method, Practice, Plan, Run) is the facility-neutrality mechanism.

Modelling lenses: ISA-95 (structural), ISA-88 (Track A, episodic procedures), ISA-106 (Track B, continuous operations), ISA-99 (Track C, trust topology), ISO/IEC 42001 + NIST AI RMF (AI governance), W3C PROV-O (provenance vocabulary at API boundaries).

Full layer-2 view: [docs/architecture.md](docs/architecture.md). For the current concrete picks (FastAPI, Postgres, Atlas, MCP SDK, etc.) and the reasoning behind each, see [docs/stack.md](docs/stack.md).
