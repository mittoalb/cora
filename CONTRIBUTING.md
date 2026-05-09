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

### File and symbol naming

- **Commands** — PascalCase nouns in `domain/commands.py` (e.g. `RegisterActor`).
- **Deciders** — snake_case verb functions in `domain/<verb>.py` matching the command's verb form (e.g. `register_actor` in `domain/register_actor.py`). Per Chassaing's decider convention.
- **Handlers** — snake_case verb factory functions in `application/<verb>_handler.py` (e.g. `make_register_actor_handler` in `application/register_actor_handler.py`). The `_handler` filename suffix disambiguates the application file from the same-verb decider file in the domain.
- **Domain errors** — PascalCase ending in `Error` (e.g. `InvalidActorNameError`, `ActorAlreadyExistsError`) per PEP 8 / ruff N818.
- **Domain events** — PascalCase past-tense verbs in `domain/events.py` (e.g. `ActorRegistered`).

## Branch + PR flow

Solo dev for now: commit directly to `main`. CI must be green before pushing.

When collaborators arrive, switch to short-lived feature branches with PRs. The convention above is what the future commitlint rule will enforce.
