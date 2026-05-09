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
- `db` — migrations, schema, event store internals
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

## Branch + PR flow

Solo dev for now: commit directly to `main`. CI must be green before pushing.

When collaborators arrive, switch to short-lived feature branches with PRs. The convention above is what the future commitlint rule will enforce.
