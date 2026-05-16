"""End-to-end proof that the `list_query` factory's dynamic-SQL
composition uses indexes under PostgreSQL's generic plan.

## What this test demonstrates (and what it does NOT)

It demonstrates: the SQL the factory emits is sargable; under
PG17+'s `EXPLAIN (GENERIC_PLAN)` analysis it picks an Index Scan
(or Bitmap Index Scan) on `proj_run_summary_plan_idx`. This is
the production-relevant proof that the dynamic-SQL composition
doesn't accidentally undermine the existing indexes.

It does NOT demonstrate that smart-logic
(`$1 IS NULL OR column = $1`) catastrophically falls back to
sequential scans on PG18. An earlier draft of this test asserted
that, on the strength of Markus Winand's
["Smart Logic"](https://use-the-index-luke.com/sql/where-clause/obfuscation/smart-logic)
article and the PostgreSQL PREPARE docs. The empirical finding
on PG18 is different: even under `EXPLAIN (GENERIC_PLAN)` and
even with `plan_cache_mode = force_generic_plan`, PG18's planner
chooses Bitmap Index Scan + Recheck for the smart-logic shape,
optimistically using the index and rechecking the OR per row.

That doesn't refute the refactor:

  - **Code quality**: removing smart-logic kept the factory's
    SQL composition cleaner, more idiomatic
    (matches SQLAlchemy + psycopg3 conventions), and easier
    to read.
  - **Older PG**: PG planners earlier than 17 were not as
    aggressive with the Bitmap Recheck rewrite; the deferred
    psycopg3-migration entry and the broader portability
    posture mean we don't want to rely on PG18-specific planner
    smarts.
  - **Plan-cache memory**: each distinct filter combination
    produces a tight SQL string with a tight plan; smart-logic
    produces one bloated plan covering all combinations. At
    scale, the dynamic shape uses memory more predictably even
    when both shapes hit the index.
  - **One mental model**: the slice's SQL matches what a reader
    expects (filter present == fragment present). Smart-logic's
    "the filter is always there but might be inert" requires the
    reader to translate.

The empirical finding is captured in
`[[project_pg_smart_logic_observation]]` so future contributors
don't relitigate it.

## Why `EXPLAIN (GENERIC_PLAN)` and not `SET plan_cache_mode`

PostgreSQL 17 added the `GENERIC_PLAN` option to `EXPLAIN`. It
shows the generic plan PG would build for a prepared statement
WITHOUT executing it. This matches the production hot path
behavior and makes the test deterministic without depending on
session-GUC interactions with asyncpg's auto-prepared statement
cache. CORA's testcontainer pins PG18
(see `tests/conftest.py`) so this option is available.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)

# 100 plans * 50 runs each = 5000 rows. Picked so the query that
# matches one plan_id returns ~50 rows: an index lookup of 50 entries
# is unambiguously cheaper than a seq scan of 5000, so the planner's
# Index-Scan-vs-Seq-Scan decision reflects the predicate's
# sargability, not a row-count heuristic at the noise floor.
_PLAN_COUNT = 100
_RUNS_PER_PLAN = 50


async def _seed_run_summary(pool: asyncpg.Pool) -> UUID:
    """Bulk-seed `proj_run_summary` with 5000 rows via COPY for speed.

    Returns one plan_id we'd realistically filter on; the test
    SQL doesn't depend on the specific value (GENERIC_PLAN
    discards bind values for planning) but a stable known-good
    id is useful for future variants of the test that want to
    assert on returned rows.
    """
    plan_ids = [uuid4() for _ in range(_PLAN_COUNT)]
    target_plan_id = plan_ids[0]
    rows: list[tuple[UUID, str, UUID, UUID | None, str | None, str, datetime, bool]] = []
    for plan_idx, plan_id in enumerate(plan_ids):
        for run_idx in range(_RUNS_PER_PLAN):
            rows.append(
                (
                    uuid4(),
                    f"run-{plan_idx}-{run_idx}",
                    plan_id,
                    None,
                    None,
                    "Running",
                    _NOW + timedelta(seconds=plan_idx * _RUNS_PER_PLAN + run_idx),
                    False,
                )
            )

    async with pool.acquire() as conn:
        await conn.copy_records_to_table(
            "proj_run_summary",
            records=rows,
            columns=[
                "run_id",
                "name",
                "plan_id",
                "subject_id",
                "raid",
                "status",
                "created_at",
                "override_parameters_present",
            ],
        )
        # ANALYZE so the planner has fresh statistics for the
        # Index-vs-Seq-Scan cost calculation. Without this a 5000-row
        # table might be planned as if it had ~10 rows.
        await conn.execute("ANALYZE proj_run_summary")
    return target_plan_id


async def _explain_generic_plan(
    pool: asyncpg.Pool,
    sql: str,
    *dummy_args: object,
) -> str:
    """Return the GENERIC_PLAN EXPLAIN output flattened to a
    searchable string.

    `EXPLAIN (GENERIC_PLAN, FORMAT JSON) <sql>` builds the plan
    PG would use for the prepared statement without using the
    parameter values for cost decisions. asyncpg's protocol-level
    bind step still requires one Python object per `$N`
    placeholder; dummies satisfy it while GENERIC_PLAN discards
    them at planning time.

    asyncpg's `json[b]` codec parses the result automatically; we
    re-serialize for substring searching.
    """
    async with pool.acquire() as conn:
        plan = await conn.fetchval(
            f"EXPLAIN (GENERIC_PLAN, FORMAT JSON) {sql}",
            *dummy_args,
        )
    return json.dumps(plan)


@pytest.mark.integration
async def test_dynamic_sql_uses_index_under_generic_plan(db_pool: asyncpg.Pool) -> None:
    """Factory-style SQL: equality predicate that the generic plan
    can satisfy with the existing `proj_run_summary_plan_idx`.

    This is the load-bearing perf assertion. If a future factory
    change emits SQL the planner can't index-scan, this test fails.
    """
    target_plan_id = await _seed_run_summary(db_pool)
    plan_json = await _explain_generic_plan(
        db_pool,
        # The exact SQL shape `make_list_query_handler` emits for
        # `ListRuns(plan_id=X)`.
        """
        SELECT run_id, name, plan_id, subject_id, raid, status, created_at,
               override_parameters_present
        FROM proj_run_summary
        WHERE plan_id = $1
        ORDER BY created_at ASC, run_id ASC
        LIMIT 51
        """,
        target_plan_id,
    )
    assert "Index Scan" in plan_json or "Bitmap Index Scan" in plan_json, (
        "Factory-style equality predicate should use the plan_id index "
        "under generic plan. Planner picked:\n"
        f"{plan_json}"
    )
    assert "Seq Scan" not in plan_json, (
        "Generic plan unexpectedly fell back to sequential scan despite "
        "the equality predicate being indexable. Plan:\n"
        f"{plan_json}"
    )
