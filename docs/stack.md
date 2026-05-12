# Implementation stack

This document is the **layer-3** view of CORA: which concrete products fill each architectural role, why each was chosen, and what would trigger a swap. The roles and patterns themselves live in [architecture.md](architecture.md). Pinned versions live in `apps/api/pyproject.toml`, `infra/docker-compose.yml`, and `Makefile`.

These picks are **starting points, not strict commitments**. Each was chosen by fit-for-purpose at the time of writing. CORA's seam discipline (ports + adapters, hexagonal layout, BC isolation) is the mechanism that lets any one of them be swapped without touching the domain core.

## Backend runtime

| Role | Current pick | Why this | Swap trigger |
| --- | --- | --- | --- |
| Language | Python 3.13 | Pyright strict mode, structural typing via `Protocol`, async-first stdlib, scientific ecosystem | Workload-specific (an embedded controls path moves to Rust); the domain core stays Python |
| HTTP framework | FastAPI | Pydantic v2 schemas, OpenAPI for free, mature async | A successor with the same Pydantic + async story (Litestar, etc.) |
| Async DB driver | asyncpg | Lowest-overhead Postgres driver; required for projection-worker throughput | A future workload that asyncpg's API can't accommodate |
| Agent-protocol SDK | `mcp` (official Python SDK) | First-party reference implementation, tracks the spec | Major MCP-spec break |
| Validation | Pydantic v2 | The de facto standard for FastAPI schemas; fast, mature | Coupled to the HTTP framework choice |
| Settings / config | pydantic-settings | Env-var-driven `Settings` with Pydantic validation; `Settings.require_authenticated_principal` and the `APP_ENV` gate are wired this way | Coupled to the Validation choice |
| ID generation | uuid-utils (UUIDv7) | Backs the `IdGenerator` port adapter; UUIDv7 gives time-ordered keys without exposing wall-clock | A future stdlib UUIDv7 (PG18's native `uuidv7()` is rejected per non-determinism principle: handler-side injection preserves replay determinism) |
| HTTP server | Uvicorn | Standard async ASGI server; integrates with FastAPI | Hypercorn or another ASGI server if HTTP/2 or H/3 becomes a hard requirement |

## Datastore

| Role | Current pick | Why this | Swap trigger |
| --- | --- | --- | --- |
| Relational store | Postgres 18 | Single store for events + projections + idempotency + vector search; PG18's AIO subsystem gives a roughly 3× perf bump for projection-worker reads | Multi-tenant scale-out (per-tenant DB), or a workload that justifies a true streaming store (NATS JetStream, Kafka) |
| Event store | Hand-rolled on the `events` table | Total control of envelope shape, role-level immutability, transaction-id cursor | A dedicated event-store product (EventStoreDB, Marten) only when its features outweigh lock-in |
| Vector index | pgvector | Same store as everything else; sufficient for current Decision-BC reasoning embeddings | Throughput or recall pushing past pgvector's envelope |
| Schema migration tool | Atlas | Hash-verified migration directory, declarative or imperative, forward-only fits CORA policy, CI-friendly | Atlas's licence model becoming a problem |

## Authentication and authorisation

| Role | Current pick | Why this | Swap trigger |
| --- | --- | --- | --- |
| Authentication wiring | `X-Principal-Id` header behind a verifying proxy | Phase-1 dev/test fallback; production deployments front the API with a verifying proxy (Envoy, nginx, cloud gateway) that strips client-supplied principal headers and sets the verified value | Stays as the application-side contract; the proxy is where deployments swap |
| Authorisation model (planned) | ReBAC (SpiceDB or OpenFGA, undecided) | Multi-stakeholder ownership common in shared-facility settings | Locked when the first non-Cedar authz rule lands |
| Decision-BC policy language | Cedar | Used in Decision predicates such as `has_determining_policies` | Stays |

## Observability

| Role | Current pick | Why this | Swap trigger |
| --- | --- | --- | --- |
| Structured logging | structlog | JSON-rendered logs, processor pipeline for trace-context injection | Stays |
| Metrics | prometheus-client + prometheus-fastapi-instrumentator | Industry-standard scrape format, per-app `CollectorRegistry` works under repeated `TestClient` construction | A future preference for push metrics (OTLP-only) |
| Tracing | OpenTelemetry (api/sdk + asyncpg + fastapi instrumentations) | Vendor-neutral; OTel `gen_ai.*` semconv lands in Decision-BC reasoning logbooks | Stays |
| Tracing transport | OTLP over HTTP (`opentelemetry-exporter-otlp-proto-http`) | Vendor-neutral wire format; `OTEL_EXPORTER_OTLP_*` env vars are passed straight through (CORA deliberately does not shadow them) | gRPC variant if a backend requires it |

### Receivers (where the data lands in production)

CORA emits structured logs, Prometheus metrics, and OTel traces; all three production receivers are deferred today (no production deployment is live). Named so the gap is visible.

| Role | Status | Trigger |
| --- | --- | --- |
| Log aggregator | Deferred (Loki, ELK, Datadog, cloud-native) | First non-local deployment |
| Metrics scraper / store | Deferred (Prometheus server, Mimir, managed) | First non-local deployment |
| Tracing backend | Deferred (Jaeger, Tempo, Honeycomb, vendor) | First non-local deployment |
| OTel Collector | Deferred (in-process exporter vs sidecar collector) | First non-local deployment, or when more than one signal type needs preprocessing |

## Deployment and packaging

| Role | Current pick | Why this | Swap trigger |
| --- | --- | --- | --- |
| Build backend | hatchling | Standard PEP 517 backend, uv-friendly, pinned in `[build-system]` | A workspace tool requiring a different backend |
| Container image | Deferred | Not yet built; first non-local deployment will define the base image and layering | First non-local deployment |
| Runtime target | Deferred (Kubernetes, Cloud Run, ECS, bare VMs) | Not yet deployed beyond local dev | First non-local deployment |
| Image registry | Deferred (ghcr, Docker Hub, cloud-native) | Tied to the runtime-target pick | Locked alongside runtime target |

## Frontend (planned)

Not yet on disk. Picks below are the *current intent*, not a commitment.

| Role | Current pick | Why this |
| --- | --- | --- |
| Framework | Next.js 15 PWA | Server components, RSC + streaming, mature ecosystem |
| Lint + format | Biome | One tool for JS/TS lint + format; faster than ESLint + Prettier |

## Tooling

| Role | Current pick | Why this |
| --- | --- | --- |
| Python package manager | uv | One fast tool replaces pip + virtualenv + pip-tools |
| Lint + format (Python) | Ruff | One tool, fast, growing rule coverage |
| Type checker | Pyright (strict mode) | Strictest checker available; structural typing aligns with `Protocol`-based ports |
| Test runner | pytest + pytest-asyncio | De facto Python standard; `--import-mode=importlib` aligns with `src/` layout |
| HTTP test client | httpx | FastAPI's `TestClient` rides on it; used by every contract test |
| Integration test isolation | testcontainers (Postgres) | Each integration run gets a fresh Postgres instance; mirrors prod schema via Atlas |
| Import-boundary linter | tach | Enforces BC isolation at import time |
| Pre-commit framework | pre-commit | Standard Python tooling |
| Local container runtime | Docker + docker-compose | Runs Postgres + pgvector locally per Quick start; only used for local dev infra |
| CI | GitHub Actions | Repo lives on GitHub; standard workflow |

## Deferred picks

Roles where CORA has deferred the implementation choice until a real consumer demands it. Each carries an explicit trigger in `project_deferred.md` (see auto-memory). Highlights:

- **Streaming bus** (NATS JetStream vs in-process). Locked when the first cross-BC saga lands.
- **Cache layer** (Redis vs in-process). Locked when the first read pattern needs it.
- **Search index** (Meilisearch vs Postgres FTS). Locked when the first user-facing search query lands.
- **Container orchestration** (Helm, Argo CD). Locked when the first non-local deployment lands.
- **Authz engine** (SpiceDB vs OpenFGA). Locked when the first non-Cedar authz rule lands.
- **Snapshot store** (in-events vs sidecar table). Locked when fold-on-read becomes a measurable bottleneck.
- **Outbox pattern** (table-based vs NOTIFY-only). Locked when the first cross-process event consumer needs at-least-once delivery beyond the projection-worker bookmark.
- **LLM provider and embedding model** for Decision-BC reasoning generation. CORA today *stores* reasoning entries shaped by OTel `gen_ai.*` semconv but does not generate them. Locked when generation lands.
- **Backup and PITR strategy** for the relational store. Locked before any non-local deployment.
- **Secrets management** (Vault, cloud secrets manager, sealed-secrets). Today `.env.example` plus environment variables only. Locked before any non-local deployment.
- **TLS termination and load balancer** layer. Today implicit; the verifying proxy named in the auth row carries this responsibility in most deployments. Locked when a deployment chooses its proxy.
- **Documentation site generator** (mkdocs, Docusaurus, etc.). Locked if `docs/*.md` outgrows GitHub's renderer.
- **Versioning and release scheme**. `version = "0.1.0"` is in pyproject.toml; no docs on what bumps it or how releases get cut. Locked when the first external consumer of the API or library exists.
