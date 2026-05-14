# Backend

For implementers picking the server-side runtime. Each row names a role, the current pick, the reason, and the trigger that would force a swap.

## Language and runtime

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Language | Python 3.13 | Pyright strict, structural typing, async-first, scientific ecosystem | Embedded controls path may move to Rust; core stays Python |
| HTTP server | Uvicorn | Standard async ASGI; integrates with FastAPI | Hypercorn if HTTP/2 or H/3 becomes a hard requirement |

## HTTP and schemas

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| HTTP framework | FastAPI | Pydantic v2 schemas, OpenAPI for free, mature async | Successor with same Pydantic + async story (Litestar) |
| Validation | Pydantic v2 | De facto FastAPI schema standard | Coupled to HTTP framework |
| Settings | pydantic-settings | Env-var `Settings` class with Pydantic validation | Coupled to Validation |

## Persistence

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Async DB driver | asyncpg | Lowest-overhead Postgres driver; needed for projection throughput | Workload asyncpg's API can't accommodate |
| ID generation | uuid-utils (UUIDv7) | Backs `IdGenerator` port; time-ordered keys without exposing wall-clock | PG18's native `uuidv7()` rejected per non-determinism principle |

## Agent protocol

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Agent-protocol SDK | `mcp` (official Python SDK) | First-party, tracks the spec | Major MCP-spec break |
