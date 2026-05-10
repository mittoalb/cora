# Contributing to CORA

## Commit messages — Conventional Commits with scope

Format: `type(scope): subject`

Subject is imperative, lowercase, no trailing period, under 72 characters.

### Allowed types

| Type       | Use for                                                            |
| ---------- | ------------------------------------------------------------------ |
| `feat`     | New feature or capability visible to a caller                      |
| `fix`      | Bug fix                                                            |
| `refactor` | Internal restructure with no behavioral change                     |
| `perf`     | Performance improvement                                            |
| `test`     | Add or amend tests only                                            |
| `docs`     | Documentation only                                                 |
| `build`    | Build system, dependencies, packaging (`pyproject.toml`, `uv.lock`) |
| `ci`       | CI configuration (`.github/workflows/`, pre-commit, hooks)         |
| `chore`    | Anything else not user-visible (formatting sweeps, version bumps)  |

### Allowed scopes

Scopes map to bounded contexts and infrastructure layers. Use the most specific applicable scope. If a change touches multiple scopes, pick the dominant one or omit the scope.

**Infrastructure / cross-cutting:**

- `infra` — shared infrastructure (config, logging, ports, deps wiring)
- `api` — FastAPI HTTP surface, MCP entrypoints, middleware
- `db` — migrations, schema, event store internals (atlas migrations live in `infra/atlas/`)
- `obs` — observability (logging, tracing, metrics)
- `auth` — authentication wiring (distinct from the `access` BC)
- `arch` — cross-cutting architectural conventions (BC layout, file organization)

**Bounded contexts** (one scope per BC; full map in memory `project_bc_map.md`):

- `equipment`, `access`, `recipe`, `run`, `campaign`, `supply`, `operation`,
  `trust`, `data`, `subject`, `decision`, `strategy`, `budget`

**Tooling / repo:**

- `repo` — repo-level files (README, CONTRIBUTING, gitignore, Makefile)
- `deps` — dependency bumps with no other change

### Examples

```
feat(infra): add port protocols and structured logging
feat(equipment): add register_device decider with optimistic concurrency
fix(db): drop redundant index on events(stream_id)
test(access): cover register_actor invariants
ci: add lint+typecheck+test workflow
docs(repo): document scope vocabulary
build(deps): bump fastapi to 0.137.0
```

### Granularity

One commit = one cohesive change that compiles and passes tests. A commit that touches a port + adapter + test for the same capability is one commit. A commit that mixes a refactor and a feature is two commits.

## Code conventions

### Imports

Prefer **package imports** (the package's `__init__.py` re-exports the symbol) over **submodule imports**:

```python
# Preferred — uses the curated re-export surface
from cora.access.application import RegisterActorHandler, UnauthorizedError
from cora.access.domain import RegisterActor, InvalidActorNameError

# Avoid when the symbol is re-exported from the package
from cora.access.application.register_actor_handler import RegisterActorHandler
```

The package `__init__.py` is the BC's curated public surface. Importing through it lets the module layout be reorganized without ripple edits and keeps the `__all__` list honest about what's intended for external use. Reach for submodule paths only when the symbol is intentionally not re-exported (BC-internal helpers, test-only seams).

Ruff doesn't have a built-in rule for this; enforce via review.

### BC layout — vertical slice with aggregate folders

Each BC follows this two-axis layout: aggregates own the data shape; features (vertical slices) own the use cases.

```
cora/<bc>/
├── __init__.py             # re-exports public BC surface
├── _bootstrap.py           # BC-internal constants (e.g. SYSTEM_PRINCIPAL_ID)
├── _idempotency.py         # cross-cutting decorator for command handlers (BC-internal)
├── _routing.py             # shared route DI helpers (correlation_id, principal_id, ErrorResponse)
├── errors.py               # BC-application-layer errors (e.g. UnauthorizedError)
├── routes.py               # register_<bc>_routes(app): include slice routers + exception handlers
├── tools.py                # register_<bc>_tools(mcp, *, get_handlers)
├── wire.py                 # <Bc>Handlers bundle + wire_<bc>(deps), applies cross-cutting decorators
├── aggregates/
│   └── <aggregate>/        # one folder per aggregate root
│       ├── __init__.py     # re-exports
│       ├── state.py        # aggregate state + value objects + domain errors
│       ├── events.py       # event classes + ActorEvent union + to_payload + from_stored + to_new_event
│       ├── evolver.py      # evolve(state, event) + fold(events)
│       └── read.py         # load_<aggregate>(event_store, id) -> Aggregate | None  (fold-on-read)
└── features/
    ├── <verb>_<aggregate>/ # one folder per COMMAND (vertical slice)
    │   ├── __init__.py     # re-exports for module-as-namespace
    │   ├── command.py      # the command dataclass
    │   ├── decider.py      # pure decide(state, command, *, now, new_id) -> events
    │   ├── handler.py      # bind(deps) -> Handler + IdempotentHandler Protocol
    │   ├── route.py        # APIRouter + Pydantic schemas
    │   └── tool.py         # MCP tool registration
    └── get_<aggregate>/    # one folder per QUERY (vertical slice, no decider)
        ├── __init__.py
        ├── query.py        # the query dataclass
        ├── handler.py      # bind(deps) -> Handler returning Aggregate | None
        ├── route.py        # GET endpoint + Pydantic response DTO
        └── tool.py         # MCP tool registration
```

Module-as-namespace: each slice's `__init__.py` re-exports its public surface so callers write `register_actor.bind(deps)` and `register_actor.Handler` rather than verbose factory names. Events live in the **aggregate folder** (not the slice) because they are intrinsic facts about the aggregate's history.

Why this shape: it pairs Modular Monolith (BCs are macro-modules) with Vertical Slice Architecture (slices are micro-units). Aggregates remain explicit so the domain doesn't fragment into use cases. Validated by Jimmy Bogard (creator of MediatR), Milan Jovanović, and the broader 2025-2026 .NET DDD community; aligned with FastAPI vertical-slice patterns.

### File and symbol naming

- **Commands** — PascalCase nouns in `features/<slice>/command.py` (e.g. `RegisterActor`).
- **Queries** — PascalCase nouns in `features/<slice>/query.py` (e.g. `GetActor`).
- **Decider** — pure function `decide` in `features/<slice>/decider.py`. Create-style: `decide(state, command, *, now, new_id)`. Update-style: `decide(state, command, *, now)`. Queries have no decider.
- **Handler** — `bind(deps) -> Handler` in `features/<slice>/handler.py`. The bare `Handler` is a `typing.Protocol`; for create/update slices that opt into idempotency, also define `IdempotentHandler` (same shape + optional `idempotency_key` kwarg). Tests use bare Handler; production wiring in `wire.py` uses the wrapped IdempotentHandler.
- **Domain errors** — PascalCase ending in `Error` (e.g. `InvalidActorNameError`, `ActorAlreadyExistsError`) per PEP 8 / ruff N818. Live in the aggregate's `state.py` if tied to the aggregate's invariants.
- **BC-application-layer errors** — also PascalCase + `Error` suffix. Live in `cora/<bc>/errors.py` (e.g. `UnauthorizedError`). Re-exported from the BC's `__init__.py` for cross-slice consumers.
- **Domain events** — PascalCase past-tense verbs in the aggregate's `events.py` (e.g. `ActorRegistered`); the same file holds the `<Aggregate>Event` discriminated union the evolver dispatches on.

### Read side — fold-on-read vs projection worker

Two patterns coexist; pick the right one per query:

- **Fold-on-read** (`aggregates/<aggregate>/read.py:load_<aggregate>`) for **single-aggregate GETs**. Loads the stream from the event store, deserializes via `from_stored`, folds with the evolver. O(events-per-stream) per read. Works for `GET /<resources>/{id}` style endpoints.
- **Projection worker** for **list / filter / search** endpoints (and high-traffic queries). A background task LISTENs on the events channel, maintains a denormalized projection table, GET reads from there. Not yet implemented; lands when the first list endpoint demands it. See `cora/access/aggregates/actor/read.py` module docstring for the trade-off.

Read repos live with the aggregate (not the slice) because they operate on the aggregate's stream regardless of which command produced the events.

### Query slices

Symmetric with command slices but with no decider (queries don't emit events) and no event production:

```
features/get_<aggregate>/
├── query.py        # GetActor(actor_id: UUID)
├── handler.py      # bind(deps) -> Handler returning Aggregate | None
├── route.py        # GET /<resource>/{id} -> 200 + DTO  (404 via HTTPException on None)
└── tool.py         # MCP tool: returns DTO on hit; raises ValueError on miss (FastMCP wraps as isError)
```

Query handlers DO call `authorize` (with AllowAllAuthorize the call is a no-op today, but the call site is in place so Phase 3 Trust BC swap is mechanical per handler instead of a sweep that risks missing handlers). Handlers return domain types (`Aggregate | None`); route + tool layers do their own DTO mapping (Pydantic primitives only — decoupled from domain VO evolution).

### Idempotency-Key — cross-cutting decorator

CORA implements the [IETF `Idempotency-Key`](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07) header pattern (Stripe / Adyen / PayPal style). The wrap is applied at `wire.py` so slices stay focused on domain logic.

**Apply to:** create-style commands (server generates the aggregate id; retries would otherwise create duplicates). Update-style commands are inherently idempotent at the domain level (second call hits an already-X-Error); apply only when cached-success-on-retry semantics are needed.

**Don't apply to:** queries (no state mutation).

**Pattern:**
```python
# In wire.py:
register_actor=with_idempotency(
    register_actor.bind(deps),
    deps.idempotency_store,
    command_name="RegisterActor",
    serialize_result=str,        # UUID -> str (jsonb-friendly)
    deserialize_result=UUID,     # str -> UUID
)
```

The slice exposes two Protocols — bare `Handler` (returned by `bind`) and `IdempotentHandler` (the wrapped form with optional `idempotency_key` kwarg). Tests use bare; production uses wrapped via wire.py. The route extracts `Idempotency-Key` via `Header(alias="Idempotency-Key")` and passes through.

`IdempotencyConflictError` (same key + different body) maps to **HTTP 422** in the BC exception handler. Key length capped at 255 chars (Stripe-documented limit). Single-phase MVP: race condition under genuinely concurrent retries documented in the port docstring; production fix is two-phase claim/complete.

MCP tools currently pass `idempotency_key=None` (no MCP standard for client retry tags).

### Production hardening conventions

These middlewares are wired in `cora/api/main.py:create_app()` and apply to every BC:

- **Body size limit** — `BodySizeLimitMiddleware` checks inbound `Content-Length`, returns 413 with `{"detail": str}`. Limit configured via `Settings.max_request_body_size_bytes` (default 1 MiB). Production deployments should ALSO enforce at the reverse proxy (nginx `client_max_body_size`); the application middleware is defense in depth.
- **Prometheus `/metrics`** — `prometheus-fastapi-instrumentator` with a per-app `CollectorRegistry` (the global REGISTRY would crash on second `TestClient(create_app())` due to duplicate-collector detection). `excluded_handlers=["/metrics"]` keeps the scrape endpoint out of its own counters; `include_in_schema=False` hides it from OpenAPI `/docs`.
- **OpenTelemetry tracing** — `cora/infrastructure/observability/` wires the SDK. `Settings.otel_exporter` selects the exporter (`none` | `console` | `otlp`); the OTLP path honours the standard `OTEL_EXPORTER_OTLP_*` env vars (we deliberately don't shadow them). `FastAPIInstrumentor` is attached per-app with `excluded_urls="health,metrics,docs,openapi.json,redoc"` so probes + scrape + docs traffic don't flood the exporter. `AsyncPGInstrumentor` runs process-wide. Trace context is the source of truth for "this request" identity: `current_correlation_id()` (in `observability.correlation`) returns `UUID(int=trace_id)` of the active span; routes and MCP tools both use it, so `event.metadata.correlation_id` always matches the distributed trace_id. Handler spans are created via `with_tracing` (composition wrapper applied in `wire.py`) — span name `<bc>.<command|query>.<command_name>`, attributes `cora.bc` + `cora.command` (or `cora.query`). The structlog `add_trace_context` processor injects `trace_id`/`span_id`/`trace_flags` into every log line emitted inside an active span.

**structlog cache nuance:** `cache_logger_on_first_use=True` (in `cora/infrastructure/logging.py`) means subsequent `configure_logging()` calls don't re-bind already-cached loggers. In tests where `build_shared_deps()` runs many times, only the first call's level/handler take effect. Acceptable for our setup (everyone uses INFO + JSONRenderer); breaks if a test tries to change log level mid-process.

### structlog log line naming

Two patterns; each cross-cutting concern uses one or the other:

- **Command / query handlers**: `<verb>.<event>` — `register_actor.start`, `register_actor.denied`, `register_actor.success`, `deactivate_actor.start`, `get_actor.start`, etc. Every handler emits at least `start` (entry, with the principal/correlation context) and either `denied` (Authorize port returned Deny) or `success` (handler completed). Failures from deciders propagate as exceptions and are logged by FastAPI's exception machinery.
- **Cross-cutting middleware / decorators**: `<concern>.<event>` — `idempotency.cache_hit`, `idempotency.cache_miss`, `idempotency.conflict`, `body_size_limit.rejected`. The `<concern>` matches the file/feature name; the `<event>` describes what happened.

**Field-name conventions** (so log search is uniform across the codebase):
- `correlation_id` — always the request correlation id (str-cast UUID)
- `causation_id` — for command handlers only: the id of the upstream event that triggered this command, when there is one. Always emitted in command-handler logs (as `null` for HTTP / MCP root calls; as a str-cast UUID when sagas / process managers pass it). Query handlers do NOT emit this field — queries don't have a causation chain. Always-emit-in-commands so log queries for "commands triggered by event X" are uniform across the codebase.
- `principal_id` — the calling principal (str-cast UUID)
- `command_name` / `query_name` — the dataclass name (e.g. "RegisterActor", "GetActor")
- `actor_id` — the Actor aggregate's id whenever an Actor is in scope (the new actor for register, the target for deactivate/get). One key for one concept.
- For other aggregates: `<aggregate>_id` (e.g. `zone_id`, `conduit_id`).

### Migrations — atlas workflow

Schema changes live in `infra/atlas/migrations/<timestamp>_<short_name>.sql`. Workflow:

```bash
make migrate-new name=add_foo   # generates a new empty migration file with timestamp
# edit the .sql file with your DDL
make migrate-hash               # updates infra/atlas/atlas.sum
make migrate-apply              # applies pending migrations to local DB
```

CI verifies `atlas.sum` is in sync (`atlas migrate hash` produces no diff) and runs a narrow grep-based safety scan on net-new migration files (blocks `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, `ALTER COLUMN ... TYPE`). Atlas's own `migrate lint` was moved behind atlas-cloud login in v0.38; the project deliberately skips that path. If you genuinely need a destructive statement, add a same-line `-- atlas:safety:allow=<reason>` comment to opt out per-line. Locally: read your migration carefully and `make migrate-apply` against a scratch DB before merging — that catches the same class of issues.

### Event-sourcing conventions

Three cross-cutting rules that all event-emitting BCs follow.

**Routing key for subscribers: `(stream_type, event_type)` — never `event_type` alone.** The `event_type` discriminator stored in `events.event_type` is the unqualified class name (`"ActorRegistered"`, etc.). Today no two BCs emit the same name, but a future collision (e.g. `Trust` emits its own `"Registered"` for some Zone lifecycle event) is plausible. Consumers (projection workers, sagas) MUST filter on the pair, not on `event_type` alone — that pre-empts the silent-misroute bug class without requiring us to namespace event types globally.

**Schema evolution policy — weak schema first, new event type for breaking changes.** Five tactics exist in the literature (Erb/Overeem et al., 2021): versioned events, weak schema, upcasting, in-place transformation, copy-and-transform. Our policy:

1. **Default: weak schema, additive only.** Add new optional fields to the event payload. The evolver / `from_stored` supplies a default when reading old events that lack the field. We don't have a worked example yet because no event has been evolved; the closest pattern in the codebase is `Actor.is_active` — but note that lives in *derived state* (the `Actor` aggregate), NOT in the `ActorRegistered` event payload. State-level fields with defaults are free; event-payload-level additions require this convention.
2. **For breaking changes (rename, type change, semantic change): introduce a new event type.** Stop emitting the old type going forward; the evolver / `from_stored` continues to handle both forever. Example: a future `ActorRenamed` would be a new event class added to the `ActorEvent` union, NOT a `name` field added to `ActorRegistered`.
3. **Upcasters only when warranted.** Once you have ≥2 breaking changes on the same logical event, a `from_stored` dispatch table that maps old shapes to new is fine; a real upcaster pipeline is overkill until you have many. The `schema_version` field on `NewEvent` / `StoredEvent` is the trigger to consult when one is built; today it's always `1` and the dispatch is by `event_type` alone.

Why this policy: events are immutable and persist forever, but value objects evolve. The evolver re-validates payloads on read by reconstructing VOs (`Actor(name=ActorName(event.name))`); that round-trip is the safety net for additive change. Breaking changes through new event types are explicit at the `ActorEvent` union level — pyright's exhaustiveness check forces you to handle the new type everywhere.

**`event_id` is the dedup key for downstream consumers.** Producers generate one fresh UUIDv7 per emitted event via the IdGenerator port; the events table has a UNIQUE constraint on `event_id`. Subscribers receive at-least-once delivery and dedupe by checking `event_id` against their local checkpoint. When polling the events table by `position`, also handle the bigserial sequence-rollback hazard documented at the top of `cora/infrastructure/ports/event_store.py` (a slow transaction can commit after a faster one with a higher position; naive `WHERE position > watermark` polling skips it).

### HTTP error idiom — HTTPException in routes, JSONResponse in exception handlers

Two distinct contexts, two distinct rules — easy to conflate:

- **Inside route functions** — raise `HTTPException(status_code=..., detail=...)`. This is the FastAPI idiom; it's purpose-built and accepts JSON-serializable detail. Use for in-band errors a route detects directly (e.g. a query handler returns `None` and the route maps it to 404).
- **Inside `app.add_exception_handler(...)` callbacks** — return `JSONResponse(...)` directly, never raise `HTTPException`. Per [FastAPI guidance](https://fastapi.tiangolo.com/tutorial/handling-errors/), raising HTTPException inside an exception handler creates nested-exception handling pitfalls.

Routes raise; handlers return. Both end up as the same JSON shape over the wire.

### Cross-cutting / shared code

Per Vertical Slice guidance, **don't extract until you have three real usages with identical, stable logic** (Rule of Three). Shared domain primitives (errors, value objects used across multiple aggregates) live at the BC root or in a `_shared/` sibling once they exist. Cross-BC concerns live under `cora/infrastructure/` (logging, config, ports, adapters).

### BC-level bootstrap constants — `_bootstrap.py`

Constants that every slice surface (REST + MCP + future gRPC / A2A) needs but that aren't slice-specific live in `cora/<bc>/_bootstrap.py`:

```python
# cora/access/_bootstrap.py
from uuid import UUID

SYSTEM_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000000")
```

Both `features/<slice>/route.py` and `features/<slice>/tool.py` import from there:

```python
from cora.access._bootstrap import SYSTEM_PRINCIPAL_ID
```

The leading underscore signals "BC-internal" — shared across slices but not part of the BC's public surface. Phase 3 (Trust BC) replaces these constants with authenticated-actor lookup; the swap is one edit per BC.

### Value objects

Value objects encapsulate domain invariants and live with the smallest scope that owns those invariants:

| Scope | Home | Example |
| --- | --- | --- |
| Tied to one aggregate's invariants | `aggregates/<aggregate>/state.py` (split into `value_objects.py` when `state.py` exceeds ~200 lines) | `ActorName` for Actor |
| Shared across aggregates **within one BC** | `<bc>/value_objects.py` (or `<bc>/_shared/`) | `ConduitName` shared by Trust's Zone + Conduit |
| Shared across **multiple BCs** | `cora/shared/value_objects.py` (Shared Kernel) | `Money`, `EmailAddress`, `PIDINST` |
| Slice-local only | almost never the right answer — promote to aggregate-VO | (none today) |

Promote a VO up the hierarchy only when it has ≥3 real usages with identical, stable invariants (Rule of Three). Premature promotion couples consumers; premature inlining duplicates invariant logic.

**Primitives in event payloads, VOs at state and decider boundaries.** Events MUST carry primitive types (str, int, UUID, datetime, dict) — never Pydantic models or dataclass VOs. Reasons:

- Events are immutable and persist forever; VOs evolve. Adding an invariant to `ActorName` after `ActorRegistered` events with old-shape names exist would make those events un-deserializable on replay.
- Events get serialized to jsonb; primitive-only payloads survive any storage format change.
- Decider takes VO-typed state but unwraps when constructing events: `ActorRegistered(name=actor_name.value)` not `ActorRegistered(name=actor_name)`.
- The evolver re-validates by re-constructing the VO when folding the event back into state: `Actor(name=ActorName(event.name))`. This is the round-trip safety net.

This pattern is canonical in event-sourcing literature ([Nick Chamberlain — "Why we Avoid Putting Value Objects in Events"](https://buildplease.com/pages/vos-in-events/), [event-driven.io — "Explicit events serialisation"](https://event-driven.io/en/explicit_events_serialisation_in_event_sourcing/)). The decider+evolver round-trip test under `tests/unit/<bc>/test_evolver.py` verifies it for each aggregate.

## Branch + PR flow

Solo dev for now: commit directly to `main`. CI must be green before pushing.

When collaborators arrive, switch to short-lived feature branches with PRs. The convention above is what the future commitlint rule will enforce.
