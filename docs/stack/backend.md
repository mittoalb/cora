# Backend

*Language, HTTP, async DB, agent SDK, validation, settings, IDs, server.*

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Language | Python 3.13 | Pyright strict, structural typing, async-first, scientific ecosystem | Embedded controls path may move to Rust; core stays Python |
| HTTP framework | FastAPI | Pydantic v2 schemas, OpenAPI for free, mature async | Successor with same Pydantic + async story (Litestar) |
| Async DB driver | asyncpg | Lowest-overhead Postgres driver; needed for projection throughput | Workload asyncpg's API can't accommodate |
| Agent-protocol SDK | `mcp` (official Python SDK) | First-party, tracks the spec | Major MCP-spec break |
| Validation | Pydantic v2 | De facto FastAPI schema standard | Coupled to HTTP framework |
| Settings | pydantic-settings | Env-var `Settings` with Pydantic validation; `require_authenticated_principal` + `APP_ENV` gate wired this way | Coupled to Validation |
| ID generation | uuid-utils (UUIDv7) | Backs `IdGenerator` port; time-ordered keys without exposing wall-clock | PG18's native `uuidv7()` rejected per non-determinism principle |
| HTTP server | Uvicorn | Standard async ASGI; integrates with FastAPI | Hypercorn if HTTP/2 or H/3 becomes a hard requirement |
