# Workflow

*Reading order, commits, branch flow, migrations, tests.*

The mechanics a contributor (human or LLM) has to internalise before touching the code. Each section is the rule, not the rationale; rationale lives next to the artifact it constrains.

## Reading order

Stop at any step and you have a working mental model of the layer above.

1. **One vertical slice end-to-end:** [features/register_actor/](https://github.com/xmap/cora/tree/main/apps/api/src/cora/access/features/register_actor). Five files, ~430 lines. `command.py` (input), `decider.py` (pure rule), `handler.py` (shell), `route.py` + `tool.py` (REST + MCP). Every slice follows this shape.
2. **The aggregate:** [aggregates/actor/](https://github.com/xmap/cora/tree/main/apps/api/src/cora/access/aggregates/actor). State, events, evolver. Pure.
3. **The ports:** [infrastructure/ports/](https://github.com/xmap/cora/tree/main/apps/api/src/cora/infrastructure/ports). Six `Protocol`s (clock, id_generator, event_store, idempotency, authorize, event_publisher).
4. **One fitness test:** [test_slice_contract.py](https://github.com/xmap/cora/blob/main/apps/api/tests/architecture/test_slice_contract.py). What's enforced mechanically.
5. **Vocabulary:** [Glossary](glossary.md).

## Commits

Conventional Commits with scope: `type(scope): subject`. Imperative, lowercase, no trailing period, under 72 chars.

**Types:**

| Type | Use for |
| --- | --- |
| `feat` | New caller-visible capability |
| `fix` | Bug fix |
| `refactor` | Internal restructure, no behavior change |
| `perf` | Performance |
| `test` | Tests only |
| `docs` | Docs only |
| `build` | Build, deps, packaging |
| `ci` | CI, pre-commit, hooks |
| `chore` | Anything else not user-visible |

**Scopes:**

- *Cross-cutting*: `infra`, `api`, `db`, `obs`, `auth`, `arch`
- *BCs*: `equipment`, `access`, `recipe`, `run`, `campaign`, `supply`, `operation`, `trust`, `data`, `subject`, `decision`, `strategy`, `budget`
- *Repo*: `repo`, `deps`

Multiple scopes: pick the dominant or omit.

**Examples:**

```
feat(infra): add port protocols and structured logging
feat(equipment): add register_device decider with optimistic concurrency
fix(db): drop redundant index on events(stream_id)
test(access): cover register_actor invariants
ci: add lint+typecheck+test workflow
```

**Granularity:** one commit = one cohesive change that compiles and passes tests. Port + adapter + test for one capability is one commit. Refactor + feature is two.

## Branch flow

Solo: commit directly to `main`. CI must be green before pushing.

## Migrations

Schema changes in `infra/atlas/migrations/<timestamp>_<short_name>.sql`.

```bash
make migrate-new name=add_foo   # new empty migration
# edit the .sql file
make migrate-hash               # update infra/atlas/atlas.sum
make migrate-apply              # apply locally
```

CI verifies `atlas.sum` and runs a grep-based safety scan on net-new files (blocks `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`, `ALTER COLUMN ... TYPE`). Atlas's `migrate lint` is behind atlas-cloud login (skipped). For genuine destructives, add `-- atlas:safety:allow=<reason>` per line. Forward-only: a rollback is a new compensating migration.

## Tests

Descriptive-sentence pytest style: snake_case prefixed with `test_`. Adapts Roy Osherove's `MethodName_Scenario_ExpectedBehavior` to Python.

```
test_<subject>_<expected_outcome>[_<scenario>]
```

- **subject**: unit under test (endpoint, function, layer, behavior)
- **expected_outcome**: the property pinned, not the inputs
- **scenario** (optional): conditions; introduce with `when_` or `for_`

Optimize for the property, not the inputs.

**Good:**

```
test_decide_emits_method_defined_when_stream_is_empty
test_handler_returns_capability_for_known_id
test_evolve_asset_relocated_mutates_parent_id_to_target
test_post_methods_returns_201_with_method_id
```

**Avoid:**

```
test_post_methods_with_three_capabilities_in_order_b_a_c   # describes inputs
test_handler_3                                              # opaque
test_register_subject_works                                 # outcome too vague
```

**Markers:**

- `@pytest.mark.unit`: pure / in-process
- `@pytest.mark.integration`: real Postgres via `db_pool`
- `@pytest.mark.contract`: `TestClient(create_app())`

Marker is the category; name is the property. Don't repeat the category in the name. Long names are fine.
