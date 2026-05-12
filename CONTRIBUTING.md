# Contributing to CORA

This file is the **layer-3** view of CORA: the operational conventions for working in the repo. It names specific products (FastAPI, Postgres, Atlas, MCP SDK, structlog, etc.) because the conventions are written against those concrete tools. For the architecture-level view (patterns, roles, no products) see [docs/architecture.md](docs/architecture.md). For the per-pick reasoning and swap triggers see [docs/stack.md](docs/stack.md).

## Contents

- [Reading order for newcomers](#reading-order-for-newcomers)
- [Commit messages](#commit-messages-conventional-commits-with-scope)
  - [Allowed scopes](#allowed-scopes)
- [Code conventions](#code-conventions)
  - [Imports](#imports)
  - [BC layout](#bc-layout-vertical-slice-with-aggregate-folders)
  - [File and symbol naming](#file-and-symbol-naming)
  - [Query slices](#query-slices)
  - [Projection-worker pattern](#projection-worker-pattern-phase-8e)
  - [Idempotency-Key](#idempotency-key-cross-cutting-decorator)
  - [Production hardening](#production-hardening-conventions)
  - [Test naming](#test-naming)
  - [Migrations](#migrations-atlas-workflow)
  - [Event-sourcing conventions](#event-sourcing-conventions)
  - [Cross-aggregate validation](#cross-aggregate-validation-handler-pre-loads-decider-stays-pure)
  - [HTTP error idiom](#http-error-idiom-httpexception-in-routes-jsonresponse-in-exception-handlers)
  - [Value objects](#value-objects)
- [Branch + PR flow](#branch--pr-flow)

## Reading order for newcomers

If you've never touched this repo, read in this order. Stop at any point and you'll have a working mental model of the layer above.

1. **One vertical slice end-to-end:** [apps/api/src/cora/access/features/register_actor/](apps/api/src/cora/access/features/register_actor/). Five files, ~430 lines total. `command.py` defines the input. `decider.py` is the pure business rule. `handler.py` is the imperative shell. `route.py` and `tool.py` mount the same handler on REST and MCP. Every BC slice in the repo follows this shape.
2. **The aggregate it acts on:** [apps/api/src/cora/access/aggregates/actor/](apps/api/src/cora/access/aggregates/actor/). State, events, evolver. Pure.
3. **The ports the handler depends on:** [apps/api/src/cora/infrastructure/ports/](apps/api/src/cora/infrastructure/ports/). Six `Protocol`s (clock, id_generator, event_store, idempotency, authorize, event_publisher). All side effects enter the core through these.
4. **One architecture-fitness test:** [apps/api/tests/architecture/test_slice_contract.py](apps/api/tests/architecture/test_slice_contract.py). Shows what's enforced about every slice mechanically rather than by review.
5. **The vocabulary, if anything was unfamiliar:** [docs/glossary.md](docs/glossary.md).

The rest of this file is conventions: commit messages, BC layout, naming, idempotency, logging, migrations.

## Commit messages: Conventional Commits with scope

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

- `infra`: shared infrastructure (config, logging, ports, deps wiring)
- `api`: FastAPI HTTP surface, MCP entrypoints, middleware
- `db`: migrations, schema, event store internals (atlas migrations live in `infra/atlas/`)
- `obs`: observability (logging, tracing, metrics)
- `auth`: authentication wiring (distinct from the `access` BC)
- `arch`: cross-cutting architectural conventions (BC layout, file organization)

**Bounded contexts** (one scope per BC; full map in memory `project_bc_map.md`):

- `equipment`, `access`, `recipe`, `run`, `campaign`, `supply`, `operation`,
  `trust`, `data`, `subject`, `decision`, `strategy`, `budget`

**Tooling / repo:**

- `repo`: repo-level files (README, CONTRIBUTING, gitignore, Makefile)
- `deps`: dependency bumps with no other change

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
# Preferred: uses the curated re-export surface
from cora.access.application import RegisterActorHandler, UnauthorizedError
from cora.access.domain import RegisterActor, InvalidActorNameError

# Avoid when the symbol is re-exported from the package
from cora.access.application.register_actor_handler import RegisterActorHandler
```

The package `__init__.py` is the BC's curated public surface. Importing through it lets the module layout be reorganized without ripple edits and keeps the `__all__` list honest about what's intended for external use. Reach for submodule paths only when the symbol is intentionally not re-exported (BC-internal helpers, test-only seams).

Ruff doesn't have a built-in rule for this; enforce via review.

### BC layout: vertical slice with aggregate folders

Each BC follows this two-axis layout: aggregates own the data shape; features (vertical slices) own the use cases.

```
cora/<bc>/
├── __init__.py             # re-exports public BC surface
├── _bootstrap.py           # BC-internal constants (re-exports SYSTEM_PRINCIPAL_ID from infra)
├── errors.py               # BC-application-layer errors (e.g. UnauthorizedError)
├── routes.py               # register_<bc>_routes(app): include slice routers + exception handlers
├── tools.py                # register_<bc>_tools(mcp, *, get_handlers)
├── wire.py                 # <Bc>Handlers bundle + wire_<bc>(deps), applies cross-cutting decorators
├── aggregates/
│   └── <aggregate>/        # one folder per aggregate root
│       ├── __init__.py     # re-exports
│       ├── state.py        # aggregate state + value objects + domain errors
│       ├── events.py       # event classes + <Aggregate>Event union + event_type_name + to_payload + from_stored
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

- **Commands**: PascalCase verb+noun in `features/<slice>/command.py` (e.g. `RegisterActor`). The verb signals intent; pick by the convention below.
- **Define vs Register convention**: `Define<X>` for **type / template / configuration aggregates** (Zone, Conduit, Policy, Capability: things that are *defined* once, possibly versioned later, and referenced by other aggregates as a contract); `Register<X>` for **instance aggregates** (Actor, Subject, Asset: things that exist in the world and are *recorded* into the system). The genesis event mirrors the verb (`<X>Defined` vs `<X>Registered`). When adding a new aggregate, ask: am I describing a kind/type/policy that other things will conform to (Define), or am I recording a concrete instance with its own identity (Register)? Surfaced naturally across 7 aggregates by Phase 5b; locked here so future BCs don't drift.
- **Queries**: PascalCase nouns in `features/<slice>/query.py` (e.g. `GetActor`).
- **Decider**: pure function `decide` in `features/<slice>/decider.py`. Create-style: `decide(state, command, *, now, new_id)`. Update-style: `decide(state, command, *, now)`. Queries have no decider.
- **Handler**: `bind(deps) -> Handler` in `features/<slice>/handler.py`. The bare `Handler` is a `typing.Protocol`; for create/update slices that opt into idempotency, also define `IdempotentHandler` (same shape + optional `idempotency_key` kwarg). Tests use bare Handler; production wiring in `wire.py` uses the wrapped IdempotentHandler.
- **Domain errors**: PascalCase ending in `Error` (e.g. `InvalidActorNameError`, `ActorAlreadyExistsError`) per PEP 8 / ruff N818. Live in the aggregate's `state.py` if tied to the aggregate's invariants.
- **BC-application-layer errors**: also PascalCase + `Error` suffix. Live in `cora/<bc>/errors.py` (e.g. `UnauthorizedError`). Re-exported from the BC's `__init__.py` for cross-slice consumers. Two BCs MAY define same-named errors (`cora.access.errors.UnauthorizedError` and `cora.trust.errors.UnauthorizedError` are distinct classes), and `app.add_exception_handler` keys on exact class identity, so each BC registers its own handler and a denial logs against the BC that issued it. Don't share via cross-BC import; that would couple two BCs through their failure surface.
- **Domain events**: PascalCase past-tense verbs in the aggregate's `events.py` (e.g. `ActorRegistered`); the same file holds the `<Aggregate>Event` discriminated union the evolver dispatches on.

### Read side: fold-on-read vs projection worker

Two patterns coexist; pick the right one per query:

- **Fold-on-read** (`aggregates/<aggregate>/read.py:load_<aggregate>`) for **single-aggregate GETs**. Loads the stream from the event store, deserializes via `from_stored`, folds with the evolver. O(events-per-stream) per read. Works for `GET /<resources>/{id}` style endpoints.
- **Projection worker** for **list / filter / search** endpoints (and high-traffic queries). A background task LISTENs on the `events` channel, maintains a denormalized projection table, GET reads from there. **Shipped in Phase 8e.** See "Projection-worker pattern" section below for the full contract; `cora/access/aggregates/actor/read.py` module docstring covers the fold-on-read vs projection trade-off for the per-aggregate get-by-id case.

Read repos live with the aggregate (not the slice) because they operate on the aggregate's stream regardless of which command produced the events.

### Query slices

Symmetric with command slices but with no decider (queries don't emit events) and no event production. Two shapes today:

**`get_<aggregate>` for single-resource reads by id:**
```
features/get_<aggregate>/
├── query.py        # GetActor(actor_id: UUID)
├── handler.py      # bind(deps) -> Handler returning Aggregate | None
├── route.py        # GET /<resource>/{id} -> 200 + DTO  (404 via HTTPException on None)
└── tool.py         # MCP tool: returns DTO on hit; raises ValueError on miss (FastMCP wraps as isError)
```

Reads via fold-on-read (`load_<aggregate>(event_store, id)`). Returns domain types; route + tool do their own Pydantic DTO mapping (decoupled from domain VO evolution).

**`list_<aggregates>` for keyset-paginated lists backed by a projection (Phase 8e+):**
```
features/list_<aggregates>/
├── query.py        # ListActors(cursor, limit, status)
├── handler.py      # bind(deps) -> Handler returning ActorListPage(items, next_cursor)
├── route.py        # GET /<resource>?cursor=...&limit=50&status=active -> 200 + page DTO
└── tool.py         # MCP tool with structured output
```

Reads from `proj_<bc>_<name>` directly via `deps.pool` (not from the event store; the projection worker keeps the read model fresh). Cursor format is opaque base64 of `(created_at, UUID)` per the locked Phase-8e D9 convention; encode/decode via `cora.infrastructure.projection.encode_cursor` / `decode_cursor`. Default page size 50, max 100. Status filters use `Literal[...]`; omitting the param returns all (no magic 'all' value). Empty result is 200 with `{"items": [], "next_cursor": null}`, never 404. Malformed cursor maps to 422 via `InvalidCursorError` registered in Access's exception handlers (the cross-BC infra-error registration BC).

Query handlers DO call `authorize` with the query name as `command_name` (`"GetActor"`, `"ListActors"`, etc.). Today's Trust BC gates at the command-name granularity; per-row scoping for list endpoints requires ReBAC and is deferred (`memory/project_deferred.md` "BOLA per-row scoping for list endpoints").

### Projection-worker pattern (Phase 8e)

Shipped infrastructure: `cora.infrastructure.projection`. The composition root spawns one in-process projection worker via the FastAPI lifespan; the worker advances every registered `Projection` along the event stream and maintains its `proj_<bc>_<name>` read-model table.

**Public concepts:**

- **`Projection` Protocol**: what BC authors implement. Lives in `cora/<bc>/projections/<name>.py`. Three pieces: `name` (str class attribute, must match the `proj_*` table name AND the bookmark row), `subscribed_event_types` (frozenset of event-type strings the projection cares about; pushed down to the worker's SQL filter), and `apply(event, conn)` (the read-model mutation). The advance query orders by `(transaction_id, position)` and uses `pg_snapshot_xmin(...)` exclusion to skip in-flight transactions (Khyst + Dudycz canonical pattern).
- **`apply()` MUST be idempotent**: the framework delivers at-least-once. Standard pattern: `INSERT ... ON CONFLICT (key) DO NOTHING/UPDATE`, OR an explicit `# idempotent: <reason>` comment when the operation is naturally idempotent (UPDATE-to-same-value, etc.). The arch-fitness test `tests/architecture/test_projection_idempotency.py` enforces a marker is present.
- **Per-BC registration**: each BC exports `register_<bc>_projections(registry, deps)` from its top-level `__init__.py`. The composition root (`cora/api/main.py` lifespan) calls it after `wire_<bc>(deps)` to populate the worker's `ProjectionRegistry`. New projection = three files in one BC's directory + one line in `register_<bc>_projections`.
- **Migration shape**: every `proj_*` table migration includes a `GRANT SELECT, INSERT, UPDATE, DELETE TO cora_app` plus an `INSERT INTO projection_bookmarks (name) VALUES ('proj_<bc>_<name>') ON CONFLICT DO NOTHING` for first-run sentinel registration. The arch-fitness test `tests/architecture/test_projection_grants.py` enforces the GRANT.

**Internal primitive:** `Subscriber` Protocol (`cora.infrastructure.projection.handler`). Today every Subscriber is a Projection; future sagas / external adapters will be additional kinds without duplicating the worker's advance machinery. Not exported publicly.

**Tests:** integration tests use `await drain_projections(pool, registry, deadline=2.0)` to advance synchronously after appending events, which avoids `asyncio.sleep` flakiness. Unit tests for the projection's `apply()` mock `asyncpg.Connection` and assert the SQL shape.

**Settings:**
- `projection_use_listen_notify: bool = True`: `ListenNotifyWakeup` (LISTEN on the `events` NOTIFY channel from migration `20260509120000`) for ~tens-of-ms wake-up latency. Flip to False for `PollOnlyWakeup` when NOTIFY's global commit `AccessExclusiveLock` causes contention (Recall.ai July 2025 trigger; `project_deferred.md` NATS entry covers the full out-of-process migration path).
- `projection_poll_interval_seconds: float = 5.0`: safety-net poll interval when NOTIFY is on; primary signal when off. Floor 0.1s.

### Idempotency-Key: cross-cutting decorator

CORA implements the [IETF `Idempotency-Key`](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07) header pattern (Stripe / Adyen / PayPal style). The decorator lives at `cora/infrastructure/idempotency.py` (cross-BC; extracted from `cora/access/` when Trust became the second consumer); the wrap is applied at each BC's `wire.py` so slices stay focused on domain logic.

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

The slice exposes two Protocols: bare `Handler` (returned by `bind`) and `IdempotentHandler` (the wrapped form with optional `idempotency_key` kwarg). Tests use bare; production uses wrapped via wire.py. The route extracts `Idempotency-Key` via `Header(alias="Idempotency-Key")` and passes through.

`IdempotencyConflictError` (same key + different body) maps to **HTTP 422** in the BC exception handler. Key length capped at 255 chars (Stripe-documented limit). Single-phase MVP: race condition under genuinely concurrent retries documented in the port docstring; production fix is two-phase claim/complete.

MCP tools currently pass `idempotency_key=None` (no MCP standard for client retry tags).

### Production hardening conventions

These middlewares are wired in `cora/api/main.py:create_app()` and apply to every BC:

- **Body size limit**: `BodySizeLimitMiddleware` checks inbound `Content-Length`, returns 413 with `{"detail": str}`. Limit configured via `Settings.max_request_body_size_bytes` (default 1 MiB). Production deployments should ALSO enforce at the reverse proxy (nginx `client_max_body_size`); the application middleware is defense in depth.
- **Prometheus `/metrics`**: `prometheus-fastapi-instrumentator` with a per-app `CollectorRegistry` (the global REGISTRY would crash on second `TestClient(create_app())` due to duplicate-collector detection). `excluded_handlers=["/metrics"]` keeps the scrape endpoint out of its own counters; `include_in_schema=False` hides it from OpenAPI `/docs`.
- **OpenTelemetry tracing**: `cora/infrastructure/observability/` wires the SDK. `Settings.otel_exporter` selects the exporter (`none` | `console` | `otlp`); the OTLP path honours the standard `OTEL_EXPORTER_OTLP_*` env vars (we deliberately don't shadow them). `FastAPIInstrumentor` is attached per-app with `excluded_urls="health,metrics,docs,openapi.json,redoc"` so probes + scrape + docs traffic don't flood the exporter. `AsyncPGInstrumentor` runs process-wide. Trace context is the source of truth for "this request" identity: `current_correlation_id()` (in `observability.correlation`) returns `UUID(int=trace_id)` of the active span; routes and MCP tools both use it, so `event.metadata.correlation_id` always matches the distributed trace_id. Handler spans are created via `with_tracing` (composition wrapper applied in `wire.py`). Span name is `<bc>.<command|query>.<command_name>`, attributes `cora.bc` + `cora.command` (or `cora.query`). The structlog `add_trace_context` processor injects `trace_id`/`span_id`/`trace_flags` into every log line emitted inside an active span.
- **Authentication: trust-the-proxy via `X-Principal-Id`**. `cora/infrastructure/routing.py:get_principal_id` extracts the calling principal's UUID from the `X-Principal-Id` header (Pydantic validates the UUID format → 422 on malformed). Header absent → behavior depends on `Settings.require_authenticated_principal`: False (Phase 1 dev/test default) falls back to `SYSTEM_PRINCIPAL_ID`; True (production posture, 8d) returns 401. The application TRUSTS the header value; there is no cryptographic verification in the app. **Production deployments MUST front the API with an auth proxy** (Envoy / nginx / Istio / cloud API gateway) that (1) verifies the caller's actual credentials (mTLS / JWT / OAuth / whatever your auth scheme is), (2) strips any client-supplied `X-Principal-Id` headers, and (3) sets `X-Principal-Id` to the verified principal UUID. Pair this with `Settings.trust_policy_id` so the configured Policy gates which principals can do what. MCP tools currently bypass header extraction (FastMCP doesn't surface request headers to tools cleanly) and use `SYSTEM_PRINCIPAL_ID` directly; a real MCP-side auth flow lands when the MCP spec's auth integration is wired.

- **Production startup gate (8d)**. `cora/api/main.py:_enforce_production_principal_policy` runs at `create_app()` construction. `Settings.app_env in {"prod", "production"}` AND `require_authenticated_principal=False` raises `RuntimeError` with a remediation message. Refusing to boot in production with the permissive default is cheaper than discovering the SYSTEM-fallback in production logs. Production deployments opt in via three env vars: `APP_ENV=prod` + `REQUIRE_AUTHENTICATED_PRINCIPAL=true` + `DATABASE_URL=postgresql://cora_app:...@.../cora` (cora_app credentials per "DB role separation" below).

- **DB role separation: cora_app + REVOKE on append-only tables (8d)**. Migration `20260512230000_init_role_cora_app.sql` creates the `cora_app` Postgres role with `SELECT + INSERT` only on `events` + every `entries_*` table, plus a belt-and-suspenders `REVOKE UPDATE, DELETE, TRUNCATE`. Production deployments connect the app pool as `cora_app`; migrations and admin scripts run as the database owner (`cora`). Turns event-store immutability from a code-review convention into a database-enforced guarantee. Two arch-fitness tests pin the contract: `tests/architecture/test_migration_revokes.py` checks every `events`/`entries_*` table has a matching REVOKE; `tests/integration/test_cora_app_role_revoke_postgres.py` opens a cora_app pool and asserts UPDATE/DELETE/TRUNCATE raise `asyncpg.InsufficientPrivilegeError`. Projection tables (`proj_*`) are mutable read models and get full DML for cora_app; `tests/architecture/test_projection_grants.py` enforces the GRANT.

**structlog cache nuance:** `cache_logger_on_first_use=True` (in `cora/infrastructure/logging.py`) means subsequent `configure_logging()` calls don't re-bind already-cached loggers. In tests where `build_kernel()` runs many times, only the first call's level/handler take effect. Acceptable for our setup (everyone uses INFO + JSONRenderer); breaks if a test tries to change log level mid-process.

### structlog log line naming

Two patterns; each cross-cutting concern uses one or the other:

- **Command / query handlers**: `<verb>.<event>`, for example `register_actor.start`, `register_actor.denied`, `register_actor.success`, `deactivate_actor.start`, `get_actor.start`. Every handler emits at least `start` (entry, with the principal/correlation context) and either `denied` (Authorize port returned Deny) or `success` (handler completed). Failures from deciders propagate as exceptions and are logged by FastAPI's exception machinery.
- **Cross-cutting middleware / decorators**: `<concern>.<event>`, for example `idempotency.cache_hit`, `idempotency.cache_miss`, `idempotency.conflict`, `body_size_limit.rejected`. The `<concern>` matches the file/feature name; the `<event>` describes what happened.

**Field-name conventions** (so log search is uniform across the codebase):
- `correlation_id`: always the request correlation id (str-cast UUID)
- `causation_id`: for command handlers only, the id of the upstream event that triggered this command, when there is one. Always emitted in command-handler logs (as `null` for HTTP / MCP root calls; as a str-cast UUID when sagas / process managers pass it). Query handlers do NOT emit this field, since queries don't have a causation chain. Always-emit-in-commands so log queries for "commands triggered by event X" are uniform across the codebase.
- `principal_id`: the calling principal (str-cast UUID)
- `command_name` / `query_name`: the dataclass name (e.g. "RegisterActor", "GetActor")
- `actor_id`: the Actor aggregate's id whenever an Actor is in scope (the new actor for register, the target for deactivate/get). One key for one concept.
- For other aggregates: `<aggregate>_id` (e.g. `zone_id`, `conduit_id`).

### Test naming

CORA's de facto test-name convention is the descriptive-sentence pytest style: a snake_case sentence prefixed with `test_`. Closest named precedent is Roy Osherove's `MethodName_Scenario_ExpectedBehavior` (from *The Art of Unit Testing*), adapted to Python conventions. It is NOT strict BDD (`should_<X>_when_<Y>`), Given/When/Then, or Gherkin. Those add ceremony without payoff for our scope.

**The rule:**

```
test_<subject>_<expected_outcome>[_<scenario>]
```

- **subject**: the unit under test: an endpoint (`post_methods`), a function (`decide`, `evolve`), a wired layer (`handler`, `wired_handler`), or a behavior (`mcp_define_method_tool`).
- **expected_outcome**: what the test pins. The assertion in property form, not the inputs.
- **scenario** (optional): when the property only holds under specific conditions; introduce with `when_` or `for_` for readability.

**Optimize for what property is being pinned, not for describing the inputs.** Reading the test name aloud should describe the test's purpose; reading the test body should describe the mechanics. If your name is mostly inputs, ask "what's the actual property I'm asserting?" and lead with that.

**Examples (good, these match what's already in the codebase):**

```
test_decide_emits_method_defined_when_stream_is_empty
test_handler_returns_capability_for_known_id
test_evolve_asset_relocated_mutates_parent_id_to_target
test_post_methods_returns_201_with_method_id
test_post_methods_same_key_and_body_returns_same_method_id
test_to_payload_sorts_needs_capabilities_deterministically
```

**Examples (avoid, input-led naming):**

```
test_post_methods_with_three_capabilities_in_order_b_a_c     # describes inputs, not property
test_handler_3                                                # opaque
test_register_subject_works                                   # outcome too vague
```

**Pytest markers** (already enforced by `pyproject.toml` config):
- `@pytest.mark.unit`: pure / in-process tests with no Postgres or HTTP
- `@pytest.mark.integration`: uses real Postgres via the `db_pool` fixture
- `@pytest.mark.contract`: uses `TestClient(create_app())` to exercise the HTTP / MCP surface end-to-end

The marker disambiguates the test's category; the name describes the property. Don't repeat the category in the name (a contract test in `tests/contract/` doesn't need `_contract_` in its name).

**Long names are acceptable.** A descriptive 10-word name is better than a cryptic 3-word name. If a name exceeds ~80 chars, see whether you're describing too many inputs (lead with the property instead) or whether the test is doing two things (split it).

### Migrations: atlas workflow

Schema changes live in `infra/atlas/migrations/<timestamp>_<short_name>.sql`. Workflow:

```bash
make migrate-new name=add_foo   # generates a new empty migration file with timestamp
# edit the .sql file with your DDL
make migrate-hash               # updates infra/atlas/atlas.sum
make migrate-apply              # applies pending migrations to local DB
```

CI verifies `atlas.sum` is in sync (`atlas migrate hash` produces no diff) and runs a narrow grep-based safety scan on net-new migration files (blocks `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, `ALTER COLUMN ... TYPE`). Atlas's own `migrate lint` was moved behind atlas-cloud login in v0.38; the project deliberately skips that path. If you genuinely need a destructive statement, add a same-line `-- atlas:safety:allow=<reason>` comment to opt out per-line. Locally: read your migration carefully and `make migrate-apply` against a scratch DB before merging. That catches the same class of issues.

### Event-sourcing conventions

Three cross-cutting rules that all event-emitting BCs follow.

**Routing key for subscribers: `(stream_type, event_type)`, never `event_type` alone.** The `event_type` discriminator stored in `events.event_type` is the unqualified class name (`"ActorRegistered"`, etc.). Today no two BCs emit the same name, but a future collision (e.g. `Trust` emits its own `"Registered"` for some Zone lifecycle event) is plausible. Consumers (projection workers, sagas) MUST filter on the pair, not on `event_type` alone, which pre-empts the silent-misroute bug class without requiring us to namespace event types globally.

**Schema evolution policy: weak schema first, new event type for breaking changes.** Five tactics exist in the literature (Erb/Overeem et al., 2021): versioned events, weak schema, upcasting, in-place transformation, copy-and-transform. Our policy:

1. **Default: weak schema, additive only.** Add new optional fields to the event payload. The evolver / `from_stored` supplies a default when reading old events that lack the field. We don't have a worked example yet because no event has been evolved; the closest pattern in the codebase is `Actor.is_active`, but note that lives in *derived state* (the `Actor` aggregate), NOT in the `ActorRegistered` event payload. State-level fields with defaults are free; event-payload-level additions require this convention.
2. **For breaking changes (rename, type change, semantic change): introduce a new event type.** Stop emitting the old type going forward; the evolver / `from_stored` continues to handle both forever. Example: a future `ActorRenamed` would be a new event class added to the `ActorEvent` union, NOT a `name` field added to `ActorRegistered`.
3. **Upcasters only when warranted.** Once you have ≥2 breaking changes on the same logical event, a `from_stored` dispatch table that maps old shapes to new is fine; a real upcaster pipeline is overkill until you have many. The `schema_version` field on `NewEvent` / `StoredEvent` is the trigger to consult when one is built; today it's always `1` and the dispatch is by `event_type` alone.

Why this policy: events are immutable and persist forever, but value objects evolve. The evolver re-validates payloads on read by reconstructing VOs (`Actor(name=ActorName(event.name))`); that round-trip is the safety net for additive change. Breaking changes through new event types are explicit at the `ActorEvent` union level, where pyright's exhaustiveness check forces you to handle the new type everywhere.

**`event_id` is the dedup key for downstream consumers.** Producers generate one fresh UUIDv7 per emitted event via the IdGenerator port; the events table has a UNIQUE constraint on `event_id`. Subscribers receive at-least-once delivery and dedupe by checking `event_id` against their local checkpoint. When polling the events table by `position`, also handle the bigserial sequence-rollback hazard documented at the top of `cora/infrastructure/ports/event_store.py` (a slow transaction can commit after a faster one with a higher position; naive `WHERE position > watermark` polling skips it).

### Cross-aggregate validation: handler pre-loads, decider stays pure

Some commands need to validate against another aggregate's state. For example, `define_plan` must check that the bound Practice + Method + Assets exist and are in compatible states (capability-superset, not deprecated, not decommissioned). Two instances live in the codebase today: `define_plan` (Phase 6e-1, with `PlanBindingContext`) and `start_run` (Phase 6f-1, with `RunStartContext`). The canonical pattern is the same shape both times:

**The handler (impure shell) loads the upstream aggregates and bundles them into a slice-local context dataclass; the pure decider takes that context as an opaque parameter and validates without I/O.**

```python
# slice/context.py: slice-local cross-aggregate snapshot
@dataclass(frozen=True)
class PlanBindingContext:
    practice: Practice
    method: Method
    assets: dict[UUID, Asset]


# slice/handler.py: handler does the loads
practice = await load_practice(deps.event_store, command.practice_id)
if practice is None:
    raise PracticeNotFoundError(command.practice_id)
method = await load_method(deps.event_store, practice.method_id)
if method is None:
    raise MethodNotFoundError(practice.method_id)
assets: dict[UUID, Asset] = {}
for asset_id in sorted(command.asset_ids, key=str):
    asset = await load_asset(deps.event_store, asset_id)
    if asset is None:
        raise AssetNotFoundError(asset_id)
    assets[asset_id] = asset

context = PlanBindingContext(practice=practice, method=method, assets=assets)
events = decide(state=None, command=command, context=context, now=now, new_id=new_id)


# slice/decider.py: decider stays pure; validates context as plain data
def decide(
    state: Plan | None,
    command: DefinePlan,
    *,
    context: PlanBindingContext,
    now: datetime,
    new_id: UUID,
) -> list[PlanDefined]:
    if context.practice.status is PracticeStatus.DEPRECATED:
        raise PracticeDeprecatedError(context.practice.id)
    # ... (rest of validation)
```

**Why:**

- **Decider stays pure.** No `await`, no `event_store`, no port injection. `decide(state, command, *, context, now, new_id)` is referentially transparent: same inputs always produce same outputs. Unit tests construct contexts directly with hand-built domain objects; no I/O mocking required.
- **Capture, don't recompute.** Bind-time data captured in the event payload as audit snapshots so replay never needs to re-load (and so the audit trail is reproducible even after upstream aggregates evolve). See [Plan's `PlanDefined` event](apps/api/src/cora/recipe/aggregates/plan/events.py) for the snapshot shape pattern.
- **Eventual-consistency stance preserved.** Concurrent upstream changes between handler-load and event-append are accepted; no cross-aggregate stream-version checks. Same precedent as everywhere else in CORA.
- **Existence vs state-of-existence cleanly split.** Handler raises `<X>NotFoundError` for missing referenced aggregates; decider raises domain errors (`PracticeDeprecatedError`, `AssetDecommissionedError`, etc.) for "exists but state forbids the operation". Maps cleanly to HTTP: 404 for not-found, 409 for state-conflict.
- **Slice-local context.** Each cross-validating slice gets its own `<slice>/context.py` module: `define_plan` ships `PlanBindingContext` (Practice + Method + assets), `start_run` ships `RunStartContext` (Plan + optional Subject + assets). Two distinct shapes today; promote to a shared form only after the Rule of Three (and only if the third instance shares structure with one of the existing two, since convergence isn't guaranteed).

This pattern matches the modern functional-DDD consensus (Functional Core / Imperative Shell): *"Any data that isn't in the stream (credit limits, holiday calendars, FX rates) is fetched in the imperative shell before the pure core runs and is passed in as plain values"* ([Beyond Aggregates: Lean, Functional Event Sourcing](https://ricofritzsche.me/functional-event-sourcing/)).

### HTTP error idiom: HTTPException in routes, JSONResponse in exception handlers

Two distinct contexts, two distinct rules, easy to conflate:

- **Inside route functions**: raise `HTTPException(status_code=..., detail=...)`. This is the FastAPI idiom; it's purpose-built and accepts JSON-serializable detail. Use for in-band errors a route detects directly (e.g. a query handler returns `None` and the route maps it to 404).
- **Inside `app.add_exception_handler(...)` callbacks**: return `JSONResponse(...)` directly, never raise `HTTPException`. Per [FastAPI guidance](https://fastapi.tiangolo.com/tutorial/handling-errors/), raising HTTPException inside an exception handler creates nested-exception handling pitfalls.

Routes raise; handlers return. Both end up as the same JSON shape over the wire.

### Cross-cutting / shared code

Per Vertical Slice guidance, **don't extract until you have three real usages with identical, stable logic** (Rule of Three). Shared domain primitives (errors, value objects used across multiple aggregates) live at the BC root or in a `_shared/` sibling once they exist. Cross-BC concerns live under `cora/infrastructure/` (logging, config, ports, adapters).

### BC-level bootstrap constants: `_bootstrap.py`

Constants that every slice surface (REST + MCP + future gRPC / A2A) needs but that aren't slice-specific live in `cora/<bc>/_bootstrap.py`. Today the only such constant is `SYSTEM_PRINCIPAL_ID`, and its canonical home is `cora/infrastructure/routing.py`. Each BC's `_bootstrap.py` is a thin re-export:

```python
# cora/access/_bootstrap.py
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
```

MCP tools import from the BC's `_bootstrap.py` (preserves the per-BC naming for distinguishability if a future BC ever wants its own variant):

```python
from cora.access._bootstrap import SYSTEM_PRINCIPAL_ID
```

REST routes pull `SYSTEM_PRINCIPAL_ID` indirectly through `get_principal_id` in `cora.infrastructure.routing`. The leading underscore on `_bootstrap.py` signals "BC-internal", shared across slices but not part of the BC's public surface.

### Value objects

Value objects encapsulate domain invariants and live with the smallest scope that owns those invariants:

| Scope | Home | Example |
| --- | --- | --- |
| Tied to one aggregate's invariants | `aggregates/<aggregate>/state.py` (split into `value_objects.py` when `state.py` exceeds ~200 lines) | `ActorName` for Actor |
| Shared across aggregates **within one BC** | `<bc>/value_objects.py` (or `<bc>/_shared/`) | `ConduitName` shared by Trust's Zone + Conduit |
| Shared across **multiple BCs** | `cora/shared/value_objects.py` (Shared Kernel) | `Money`, `EmailAddress`, `PIDINST` |
| Slice-local only | almost never the right answer; promote to aggregate-VO | (none today) |

Promote a VO up the hierarchy only when it has ≥3 real usages with identical, stable invariants (Rule of Three). Premature promotion couples consumers; premature inlining duplicates invariant logic.

**Bounded-name VOs share a validation helper, not a base class.** `ActorName`, `MethodName`, `PlanName`, etc. (the 10 bounded-name VOs in CORA) share the same trim+length-check+raise body. The shared logic is hoisted to `cora.infrastructure.name.validate_name`, called from each VO's `__post_init__`:

```python
@dataclass(frozen=True)
class ActorName:
    value: str

    def __post_init__(self) -> None:
        trimmed = validate_name(
            self.value,
            max_length=ACTOR_NAME_MAX_LENGTH,
            error_class=InvalidActorNameError,
        )
        object.__setattr__(self, "value", trimmed)
```

Each VO keeps its own frozen dataclass type (so `isinstance` and pyright distinguish `ActorName` from `MethodName`), its own per-aggregate error class with aggregate-specific message text, and its own `MAX_LENGTH` constant in the aggregate's state module (read by both the VO and the API-boundary Pydantic schema). A shared base class would couple the 10 aggregates to one type; a class factory would weaken `isinstance` semantics. A free function avoids both. Hoisted in Phase 6e-1 after the 10th VO landed (the "first per-VO divergence OR ~10 instances" trigger from the 5a gate-review).

**Primitives in event payloads, VOs at state and decider boundaries.** Events MUST carry primitive types (str, int, UUID, datetime, dict), never Pydantic models or dataclass VOs. Reasons:

- Events are immutable and persist forever; VOs evolve. Adding an invariant to `ActorName` after `ActorRegistered` events with old-shape names exist would make those events un-deserializable on replay.
- Events get serialized to jsonb; primitive-only payloads survive any storage format change.
- Decider takes VO-typed state but unwraps when constructing events: `ActorRegistered(name=actor_name.value)` not `ActorRegistered(name=actor_name)`.
- The evolver re-validates by re-constructing the VO when folding the event back into state: `Actor(name=ActorName(event.name))`. This is the round-trip safety net.

This pattern is canonical in event-sourcing literature ([Nick Chamberlain, "Why we Avoid Putting Value Objects in Events"](https://buildplease.com/pages/vos-in-events/), [event-driven.io, "Explicit events serialisation"](https://event-driven.io/en/explicit_events_serialisation_in_event_sourcing/)). The decider+evolver round-trip test under `tests/unit/<bc>/test_evolver.py` verifies it for each aggregate.

### Field grouping: flat-then-hoist

When an aggregate has fields that conceptually belong to a group (Method's "things this Method needs", Asset's "things this Asset has", Plan's "things this Plan binds"), default to **flat fields** until ≥3 members of the group exist. Then hoist into a value-object holder.

**The rule:** flat field names with a `<group>_<member>` prefix, no nesting:

```python
# 1 member: flat (today)
@dataclass(frozen=True)
class Method:
    needs_capabilities: frozenset[UUID]

# 2 members: still flat. Premature hoist costs ceremony for no gain
@dataclass(frozen=True)
class Method:
    needs_capabilities: frozenset[UUID]
    needs_safety_quals: frozenset[UUID]

# 3+ members: hoist into a Needs VO
@dataclass(frozen=True)
class Needs:
    capabilities: frozenset[UUID]
    safety_quals: frozenset[UUID]
    operator_role: UUID | None

@dataclass(frozen=True)
class Method:
    needs: Needs
```

**Why flat-first:**

- Pydantic / FastAPI schemas read more naturally with flat fields (`{"needs_capabilities": [...]}` vs `{"needs": {"capabilities": [...]}}`); MCP tool argument lists stay flat.
- Event payloads stay flat (event schemas are append-only, harder to refactor than state).
- A wrapper class with one field is pure ceremony.
- Python attribute access can't dot-nest anyway (`needs.capabilities` requires either a wrapper class or descriptor magic).

**Why hoist at 3:** the field-list noise crosses the threshold where reading `Method` state takes a second pass to understand which fields cohere. The wrapper class becomes a documentation device, not just structural ceremony. (Same Rule-of-Three trigger we use for VO promotion above and `to_new_event` extraction in 3b-cleanup.)

**When hoisting, the migration path:**

1. Define the holder VO in `aggregates/<aggregate>/state.py`.
2. Add an additive `<group>` field on the aggregate state with the new VO type, default-constructed; KEEP the old flat fields temporarily.
3. Update the evolver to populate both flat and grouped from the same payload primitives.
4. Migrate readers (handler / route / tool) to use the grouped form.
5. In a separate cleanup commit, remove the flat fields after no readers remain.

Event payloads STAY flat throughout (`{"needs_capabilities": [...], "needs_safety_quals": [...]}`); the holder is a state-side ergonomic, not a payload-shape change. This keeps existing event streams forward-compatible without an upcaster.

## Branch + PR flow

Solo dev for now: commit directly to `main`. CI must be green before pushing.

When collaborators arrive, switch to short-lived feature branches with PRs. The convention above is what the future commitlint rule will enforce.
