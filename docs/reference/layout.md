# Layout

*BC structure, imports, naming, bootstrap, shared code.*

Two axes on purpose: aggregates own the data shape so the domain stays explicit, slices own the use cases so a feature lives in one folder. Modular Monolith on the macro side, Vertical Slice on the micro. Keeping both stops the codebase from collapsing into either pure DDD or pure feature-folders.

## BC layout

Two-axis: aggregates own data shape; features (vertical slices) own use cases.

```
cora/<bc>/
├── __init__.py             # re-exports public BC surface
├── _bootstrap.py           # BC-internal constants
├── errors.py               # BC-application-layer errors
├── routes.py               # register_<bc>_routes(app)
├── tools.py                # register_<bc>_tools(mcp, *, get_handlers)
├── wire.py                 # <Bc>Handlers bundle + wire_<bc>(deps)
├── aggregates/
│   └── <aggregate>/
│       ├── state.py        # state + value objects + domain errors
│       ├── events.py       # event classes + union + payload helpers
│       ├── evolver.py      # evolve(state, event) + fold(events)
│       └── read.py         # load_<aggregate> (fold-on-read)
└── features/
    ├── <verb>_<aggregate>/ # one folder per COMMAND
    │   ├── command.py
    │   ├── decider.py
    │   ├── handler.py
    │   ├── route.py
    │   └── tool.py
    └── get_<aggregate>/    # one folder per QUERY (no decider)
        ├── query.py
        ├── handler.py
        ├── route.py
        └── tool.py
```

Each slice's `__init__.py` re-exports its public surface so callers write `register_actor.bind(deps)`. Events live in the aggregate folder, not the slice: they're intrinsic facts about the aggregate's history.

Pairs Modular Monolith (BCs as macro-modules) with Vertical Slice (slices as micro-units). Aggregates stay explicit so the domain doesn't fragment into use cases.

## Imports

Prefer **package imports** (re-exported from `__init__.py`) over submodule imports:

```python
# Preferred
from cora.access.application import RegisterActorHandler, UnauthorizedError

# Avoid
from cora.access.application.register_actor_handler import RegisterActorHandler
```

The `__init__.py` is the BC's curated public surface; importing through it lets the layout reorganize without ripple edits. Submodule paths only when a symbol is intentionally not re-exported. Enforced by review.

## Naming

- **Commands**: PascalCase verb+noun in `command.py` (e.g. `RegisterActor`).
- **Define vs Register**: `Define<X>` for types/templates/configs (Zone, Conduit, Policy, Capability: defined once, referenced as a contract). `Register<X>` for instances (Actor, Subject, Asset: recorded). Genesis event mirrors the verb (`<X>Defined` vs `<X>Registered`).
- **Queries**: PascalCase nouns in `query.py` (e.g. `GetActor`).
- **Decider**: pure `decide` in `decider.py`. Create-style: `decide(state, command, *, now, new_id)`. Update-style: `decide(state, command, *, now)`.
- **Handler**: `bind(deps) -> Handler` in `handler.py`. Bare `Handler` is a `Protocol`; create/update slices that opt into idempotency also define `IdempotentHandler` (same shape + optional `idempotency_key`).
- **Domain errors**: PascalCase + `Error` suffix in the aggregate's `state.py` (e.g. `InvalidActorNameError`).
- **BC-application errors**: PascalCase + `Error` suffix in `cora/<bc>/errors.py` (e.g. `UnauthorizedError`). Each BC registers its own handler; same-named errors across BCs are distinct classes.
- **Domain events**: PascalCase past-tense in the aggregate's `events.py` (e.g. `ActorRegistered`). Same file holds the `<Aggregate>Event` discriminated union.

## Bootstrap

Constants every slice surface needs but that aren't slice-specific live in `cora/<bc>/_bootstrap.py`. Today: `SYSTEM_PRINCIPAL_ID`, canonically in `cora/infrastructure/routing.py`:

```python
# cora/access/_bootstrap.py
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
```

MCP tools import from `_bootstrap.py` (preserves per-BC naming); REST routes pull it indirectly via `get_principal_id`. The leading underscore signals BC-internal.

## Shared code

Don't extract until **three real usages with identical, stable logic** (Rule of Three). Shared primitives (errors, VOs across aggregates) live at the BC root or in `_shared/`. Cross-BC concerns under `cora/infrastructure/`.

### When the Rule of Three yields to local clarity

The 13 `aggregates/<aggregate>/read.py` files are 7-line near-clones that differ only in the stream-type constant and three import lines. Rule of Three was crossed long ago, but the duplication stays. A generic `load_aggregate(event_store, stream_type, from_stored, fold)` would save ~3 lines per call site at the cost of an extra parameter-passing chain — the caller still has to import the aggregate-specific `from_stored` / `fold` to pass them in. The wrappers are mechanical, stable, and locally legible: opening `aggregates/<aggregate>/read.py` shows the entire fold-on-read path for that aggregate without a hop. A 14th aggregate doesn't change the answer.

The same posture applies to other "13 mechanical near-clones" surfaces (per-aggregate `events.py` `event_type_name` / `to_payload` / `from_stored`, evolver `fold` walker): per-aggregate locality wins over a generic helper that wouldn't actually shrink the call sites.
