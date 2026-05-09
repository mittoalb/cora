# cora-api

FastAPI + MCP backend for CORA. Python 3.13.

For repo-wide context (architecture, BC map, modeling refs), see the [root README](../../README.md).

## Local dev

From the repo root, use the Makefile (`make install`, `make test`, `make dev`, etc.). It delegates here automatically.

To run uv directly inside this app:

```bash
cd apps/api
uv sync
uv run pytest
uv run uvicorn cora.api.main:app --reload
```

## Layout

```
src/cora/
├── api/             # FastAPI + MCP entrypoints
├── shared/          # cross-BC primitives (added on demand)
└── <bc>/            # bounded contexts (currently: equipment)
    ├── domain/         # pure functional core
    ├── application/    # commands, queries, integration events
    └── infrastructure/ # asyncpg adapters, port impls

tests/
├── unit/            # pure, no I/O
├── integration/     # require Postgres
├── contract/        # REST/MCP schema verification
└── e2e/             # full end-to-end
```
