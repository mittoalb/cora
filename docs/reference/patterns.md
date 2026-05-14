# Patterns

*Read side, query slices, projections, idempotency, cross-aggregate validation.*

## Read side

- **Fold-on-read** (`aggregates/<aggregate>/read.py:load_<aggregate>`) for single-aggregate `GET`. O(events-per-stream).
- **Projection worker** for list / filter / search and high-traffic queries. Background task tails the events channel; `GET` reads a denormalized table.

Read repos live with the aggregate, not the slice; they operate on the stream regardless of which command produced the events.

## Query slices

Symmetric with command slices. No decider, no events.

**`get_<aggregate>`**: single-resource read by id.

```
features/get_<aggregate>/
├── query.py        # GetActor(actor_id: UUID)
├── handler.py      # bind(deps) -> Handler returning Aggregate | None
├── route.py        # GET /<resource>/{id} -> 200 + DTO  (404 on None)
└── tool.py         # MCP tool
```

Reads via fold-on-read. Returns domain types; route + tool do their own Pydantic DTO mapping.

**`list_<aggregates>`**: keyset-paginated list backed by a projection.

```
features/list_<aggregates>/
├── query.py        # ListActors(cursor, limit, status)
├── handler.py      # bind(deps) -> Handler returning ActorListPage
├── route.py        # GET /<resource>?cursor=...&limit=50
└── tool.py         # MCP tool
```

Reads `proj_<bc>_<name>` via `deps.pool`. Cursor is opaque base64 of `(created_at, UUID)` via `encode_cursor`/`decode_cursor`. Default page 50, max 100. Empty: `200 {"items": [], "next_cursor": null}`. Malformed cursor: 422 via `InvalidCursorError`.

Query handlers DO call `authorize` with the query name as `command_name`. Per-row scoping needs ReBAC (deferred).

## Projections

`cora.infrastructure.projection`. Composition root spawns one in-process worker via FastAPI lifespan; advances every registered `Projection` along the event stream.

- **`Projection` Protocol** in `cora/<bc>/projections/<name>.py`: `name` (matches `proj_*` table + bookmark), `subscribed_event_types`, `apply(event, conn)`. Advance orders by `(transaction_id, position)` with `pg_snapshot_xmin` exclusion.
- **`apply()` MUST be idempotent** (at-least-once delivery). `INSERT ... ON CONFLICT (key) DO NOTHING/UPDATE` or `# idempotent: <reason>`. Enforced by `test_projection_idempotency.py`.
- **Per-BC registration**: each BC exports `register_<bc>_projections(registry, deps)`; composition root calls it after `wire_<bc>(deps)`.
- **Migration shape**: every `proj_*` migration includes `GRANT SELECT, INSERT, UPDATE, DELETE TO cora_app` plus `INSERT INTO projection_bookmarks (name) VALUES (...) ON CONFLICT DO NOTHING`. Enforced by `test_projection_grants.py`.

Tests use `await drain_projections(pool, registry, deadline=2.0)` instead of `asyncio.sleep`.

**Settings:**

- `projection_use_listen_notify: bool = True`: NOTIFY wake-up (~tens of ms). Flip False if commit lock contends.
- `projection_poll_interval_seconds: float = 5.0`: safety-net poll. Floor 0.1s.

## Idempotency

[IETF `Idempotency-Key`](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07) (Stripe / Adyen / PayPal). Decorator at `cora/infrastructure/idempotency.py`; wrap applied in each BC's `wire.py`.

- **Apply**: create-style commands (server generates id; retries would otherwise duplicate).
- **Skip**: queries; updates not needing cached-success-on-retry.

```python
register_actor=with_idempotency(
    register_actor.bind(deps),
    deps.idempotency_store,
    command_name="RegisterActor",
    serialize_result=str,
    deserialize_result=UUID,
)
```

Slice exposes `Handler` (bare) and `IdempotentHandler` (wrapped, optional `idempotency_key`). Tests use bare; production wires wrapped. Routes extract via `Header(alias="Idempotency-Key")`.

`IdempotencyConflictError` (same key + different body) returns 422. Key max 255 chars. Single-phase MVP; concurrent-retry race documented in the port docstring. MCP tools pass `idempotency_key=None` (no MCP standard yet).

## Cross-aggregate validation

Some commands validate against another aggregate's state (`define_plan` checks Practice + Method + Assets; `start_run` checks Plan + optional Subject + Assets).

**Handler loads upstream aggregates into a slice-local context dataclass; pure decider takes the context as opaque parameter.**

```python
# slice/context.py
@dataclass(frozen=True)
class PlanBindingContext:
    practice: Practice
    method: Method
    assets: dict[UUID, Asset]


# slice/handler.py
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


# slice/decider.py
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
```

- **Decider stays pure.** No `await`, no port injection. Tests build contexts directly.
- **Capture, don't recompute.** Bind-time data captured in the event payload; replay never re-loads.
- **Eventual consistency.** Concurrent upstream changes between handler-load and event-append are accepted.
- **Existence vs state.** Handler raises `<X>NotFoundError` (404); decider raises domain errors (409).
- **Slice-local context.** Each cross-validating slice gets `<slice>/context.py`. Promote to a shared form only after Rule of Three.

FCIS canonical: data not in the stream is fetched in the shell and passed to the pure core as plain values.

## Rejections

A slice's behavioral contract has two halves: the events the decider emits on success, and the named exceptions it raises on failure. Both are first-class. When designing a new slice, enumerate the rejection list as a peer to the event list, not as an afterthought.

**Two domain families** plus three cross-cutting families and two infra families:

| Family | Naming | HTTP | Defined in |
| --- | --- | --- | --- |
| Validation | `Invalid<Aggregate><Field>Error(ValueError)` | 400 | `aggregates/<aggregate>/state.py` |
| Not found | `<Aggregate>NotFoundError` | 404 | `aggregates/<aggregate>/state.py` |
| Already exists | `<Aggregate>AlreadyExistsError` | 409 | `aggregates/<aggregate>/state.py` |
| State transition | `<Aggregate>Cannot<Verb>Error` | 409 | `aggregates/<aggregate>/state.py` |
| Authorization | `UnauthorizedError` | 403 | `cora/<bc>/errors.py` |
| Idempotency conflict | `IdempotencyConflictError` | 422 | `cora/infrastructure/ports/` |
| Cursor parse | `InvalidCursorError` | 422 | `cora/infrastructure/projection/` |

Existence vs state per the rule above: handler raises `<X>NotFoundError` (404) when an upstream aggregate is missing entirely; decider raises `<X>Cannot<Verb>Error` (409) when state forbids the transition. Same naming convention covers both single-stream and cross-aggregate slices.

**Decider docstrings carry an `Invariants:` block** listing each rejection inline with its exception name. This is the contract; downstream readers (test author, API consumer) shouldn't have to re-derive it from the body.

```python
def decide(state: Asset | None, command: AddAssetPort, *, now: datetime) -> list[AssetPortAdded]:
    """Decide the events produced by adding a port to an existing Asset.

    Invariants:
      - State must not be None (asset must exist) -> AssetNotFoundError
      - Asset must not be Decommissioned (lifecycle gate) -> AssetCannotAddPortError
      - Port name must not already exist (strict-not-idempotent) -> AssetCannotAddPortError
    """
```

**Central exception-to-status mapping** in each BC's `routes.py`. One handler per family, registered against a tuple of error classes via a loop. Adding a new error in a family is one tuple entry, not a new handler. Loop-collapse pattern is documented in the [`access/routes.py`](https://github.com/xmap/cora/blob/main/apps/api/src/cora/access/routes.py) module docstring; Equipment / Subject / Recipe / Run / Data / Decision / Trust mirror it.

```python
for cannot_transition_cls in (AssetCannotActivateError, AssetCannotDecommissionError, ...):
    app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
```

Routes do NOT wrap handler calls in try/except. Decider raises, central handler catches, FastAPI emits the JSON response. The response body is uniform: `{"detail": str(exc)}`.

**Cross-BC infra errors** (`ConcurrencyError`, `IdempotencyConflictError`, `IdempotencyClaimLostError`, `CachedHandlerError`, `InvalidCursorError`) are registered globally by the first-booted BC (Access). Other BCs do NOT re-register them; the JSON shape is the same regardless of which BC issued the error.

**Boundary 422s via Pydantic** are NOT raised as domain errors. Required-field length / pattern / type checks (for example `reason: str = Field(min_length=1, max_length=500)`) live in the route's request model and surface as FastAPI's standard 422. When enumerating a slice's rejections at design time, list these as boundary cases (`boundary: Pydantic min_length on reason -> 422`) so the rejection list is exhaustive.
