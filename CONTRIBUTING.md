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
├── __init__.py             # re-exports register_<bc>_routes + wire_<bc> + <Bc>Handlers
├── aggregates/
│   └── <aggregate>/        # one folder per aggregate root
│       ├── __init__.py     # re-exports
│       ├── state.py        # aggregate state + value objects + domain errors
│       ├── events.py       # event classes + the discriminated union alias
│       └── evolver.py      # evolve(state, event) + fold(events)
├── features/
│   └── <verb>_<aggregate>/ # one folder per command (vertical slice)
│       ├── __init__.py     # re-exports for module-as-namespace
│       ├── command.py      # the command dataclass
│       ├── decider.py      # pure decide(state, command, *, now, new_id) -> events
│       ├── handler.py      # bind(deps) -> Handler  + UnauthorizedError
│       └── route.py        # APIRouter + Pydantic schemas for this slice
├── routes.py               # register_<bc>_routes(app): include slice routers + register exception handlers
└── wire.py                 # <Bc>Handlers bundle + wire_<bc>(deps)
```

Module-as-namespace: each slice's `__init__.py` re-exports its public surface so callers write `register_actor.bind(deps)` and `register_actor.Handler` rather than verbose factory names. Events live in the **aggregate folder** (not the slice) because they are intrinsic facts about the aggregate's history.

Why this shape: it pairs Modular Monolith (BCs are macro-modules) with Vertical Slice Architecture (slices are micro-units). Aggregates remain explicit so the domain doesn't fragment into use cases. Validated by Jimmy Bogard (creator of MediatR), Milan Jovanović, and the broader 2025-2026 .NET DDD community; aligned with FastAPI vertical-slice patterns.

### File and symbol naming

- **Commands** — PascalCase nouns in `features/<slice>/command.py` (e.g. `RegisterActor`).
- **Decider** — pure function `decide` in `features/<slice>/decider.py`. Called via `slice_module.decide(state, command, *, now, new_id)`.
- **Handler** — `bind(deps) -> Handler` in `features/<slice>/handler.py`. The `Handler` is a `typing.Protocol` defining the call signature; consumers use `slice_module.Handler` for typing and `slice_module.bind(deps)` to construct.
- **Domain errors** — PascalCase ending in `Error` (e.g. `InvalidActorNameError`, `ActorAlreadyExistsError`) per PEP 8 / ruff N818. Live in the aggregate's `state.py` if tied to the aggregate's invariants; in the slice's `handler.py` if application-layer (e.g. `UnauthorizedError`).
- **Domain events** — PascalCase past-tense verbs in the aggregate's `events.py` (e.g. `ActorRegistered`); the same file holds the `<Aggregate>Event` discriminated union the evolver dispatches on.

### Cross-cutting / shared code

Per Vertical Slice guidance, **don't extract until you have three real usages with identical, stable logic** (Rule of Three). Shared domain primitives (errors, value objects used across multiple aggregates) live at the BC root or in a `_shared/` sibling once they exist. Cross-BC concerns live under `cora/infrastructure/` (logging, config, ports, adapters).

## Branch + PR flow

Solo dev for now: commit directly to `main`. CI must be green before pushing.

When collaborators arrive, switch to short-lived feature branches with PRs. The convention above is what the future commitlint rule will enforce.
