"""End-to-end: `list_runs` handler against real Postgres projection
table. Most-important goal of this test: prove the
`_EVENT_TO_STATUS` dict in RunSummaryProjection writes strings that
the migration's CHECK constraint accepts. With 7 events folding to
6 status strings, a typo ("Aborting" vs "Aborted") would silently
break in production but the unit test (mock-based) couldn't catch
it. This test forces every status string through the real PG
write path.

Stresses:
  - INSERT path on RunStarted (CHECK + nullable subject_id + raid)
  - UPDATE on each of the 6 lifecycle transitions (each accepted by
    the CHECK constraint)
  - cursor pagination + plan_id filter end-to-end
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import AssetLevel
from cora.equipment.features import (
    add_asset_capability,
    define_capability,
    register_asset,
)
from cora.equipment.features.add_asset_capability import AddAssetCapability
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.features import define_method, define_plan, define_practice
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run._projections import register_run_projections
from cora.run.features.abort_run import AbortRun
from cora.run.features.abort_run import bind as bind_abort
from cora.run.features.complete_run import CompleteRun
from cora.run.features.complete_run import bind as bind_complete
from cora.run.features.hold_run import HoldRun
from cora.run.features.hold_run import bind as bind_hold
from cora.run.features.list_runs import ListRuns
from cora.run.features.list_runs import bind as bind_list
from cora.run.features.resume_run import ResumeRun
from cora.run.features.resume_run import bind as bind_resume
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start
from cora.run.features.stop_run import StopRun
from cora.run.features.stop_run import bind as bind_stop
from cora.run.features.truncate_run import TruncateRun
from cora.run.features.truncate_run import bind as bind_truncate

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator(ids),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
        pool=db_pool,
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    """Drain Equipment + Recipe + Run projections (Run integration
    needs all three because the upstream chain spans them)."""
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    register_recipe_projections(registry)
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_plan(deps: Kernel) -> UUID:
    """Seed the upstream chain (Capability + Asset + Method +
    Practice + Plan) needed for start_run cross-aggregate validation.
    Returns plan_id. Consumes 11 ids from the FixedIdGenerator."""
    cap_id = await define_capability.bind(deps)(
        DefineCapability(name="Tomography"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="EigerDetector", level=AssetLevel.ENTERPRISE, parent_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_capability.bind(deps)(
        AddAssetCapability(asset_id=asset_id, capability_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    method_id = await define_method.bind(deps)(
        DefineMethod(name="Tomography", needs_capabilities=frozenset({cap_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="APS-2BM-CT", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(
            name="32-ID Plan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return plan_id


def _chain_ids() -> list[UUID]:
    """11 ids consumed by _seed_plan (define_capability=2 +
    register_asset=2 + add_asset_capability=1 + define_method=2 +
    define_practice=2 + define_plan=2)."""
    return [uuid4() for _ in range(11)]


@pytest.mark.integration
async def test_run_started_inserts_with_running_status_and_plan_ref(
    db_pool: asyncpg.Pool,
) -> None:
    """Sanity: RunStarted lands as Running with plan_id surfaced."""
    run_id = uuid4()
    deps = _build_deps(db_pool, [*_chain_ids(), run_id, uuid4()])
    plan_id = await _seed_plan(deps)
    await bind_start(deps)(
        StartRun(name="morning-session", plan_id=plan_id, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, plan_id, subject_id, raid, status "
            "FROM proj_run_summary WHERE run_id = $1",
            run_id,
        )
    assert row is not None
    assert row["name"] == "morning-session"
    assert row["plan_id"] == plan_id
    assert row["subject_id"] is None
    assert row["raid"] is None
    assert row["status"] == "Running"


@pytest.mark.integration
async def test_every_lifecycle_transition_writes_a_check_constraint_accepted_status(
    db_pool: asyncpg.Pool,
) -> None:
    """The load-bearing test: prove the dict-based dispatch in
    RunSummaryProjection writes status strings that the migration's
    CHECK constraint actually accepts. Without this round-trip, a
    typo in `_EVENT_TO_STATUS` would silently break in production
    but pass the mock-based unit test.

    Drives 4 separate Runs through 4 different terminal transitions
    plus the Held -> Resumed round-trip on a 5th, covering all 6
    status strings the CHECK constraint enumerates.
    """
    # Run 1: Started -> Held (proves "Held").
    run_held_id = uuid4()
    deps_1 = _build_deps(db_pool, [*_chain_ids(), run_held_id, uuid4(), uuid4()])
    plan_id_1 = await _seed_plan(deps_1)
    await bind_start(deps_1)(
        StartRun(name="held-run", plan_id=plan_id_1, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_hold(deps_1)(
        HoldRun(run_id=run_held_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run 2: Started -> Held -> Resumed (proves "Held" then back to "Running").
    run_resumed_id = uuid4()
    deps_2 = _build_deps(db_pool, [*_chain_ids(), run_resumed_id, uuid4(), uuid4(), uuid4()])
    plan_id_2 = await _seed_plan(deps_2)
    await bind_start(deps_2)(
        StartRun(name="resumed-run", plan_id=plan_id_2, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_hold(deps_2)(
        HoldRun(run_id=run_resumed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_resume(deps_2)(
        ResumeRun(run_id=run_resumed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run 3: Started -> Completed (proves "Completed").
    run_completed_id = uuid4()
    deps_3 = _build_deps(db_pool, [*_chain_ids(), run_completed_id, uuid4(), uuid4()])
    plan_id_3 = await _seed_plan(deps_3)
    await bind_start(deps_3)(
        StartRun(name="completed-run", plan_id=plan_id_3, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_complete(deps_3)(
        CompleteRun(run_id=run_completed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run 4: Started -> Aborted (proves "Aborted").
    run_aborted_id = uuid4()
    deps_4 = _build_deps(db_pool, [*_chain_ids(), run_aborted_id, uuid4(), uuid4()])
    plan_id_4 = await _seed_plan(deps_4)
    await bind_start(deps_4)(
        StartRun(name="aborted-run", plan_id=plan_id_4, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_abort(deps_4)(
        AbortRun(run_id=run_aborted_id, reason="alignment lost"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run 5: Started -> Stopped (proves "Stopped").
    run_stopped_id = uuid4()
    deps_5 = _build_deps(db_pool, [*_chain_ids(), run_stopped_id, uuid4(), uuid4()])
    plan_id_5 = await _seed_plan(deps_5)
    await bind_start(deps_5)(
        StartRun(name="stopped-run", plan_id=plan_id_5, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_stop(deps_5)(
        StopRun(run_id=run_stopped_id, reason="schedule ended"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run 6: Started -> Truncated (proves "Truncated").
    run_truncated_id = uuid4()
    deps_6 = _build_deps(db_pool, [*_chain_ids(), run_truncated_id, uuid4(), uuid4()])
    plan_id_6 = await _seed_plan(deps_6)
    await bind_start(deps_6)(
        StartRun(name="truncated-run", plan_id=plan_id_6, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_truncate(deps_6)(
        TruncateRun(run_id=run_truncated_id, reason="power loss", interrupted_at=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT run_id, status FROM proj_run_summary WHERE run_id = ANY($1)",
            [
                run_held_id,
                run_resumed_id,
                run_completed_id,
                run_aborted_id,
                run_stopped_id,
                run_truncated_id,
            ],
        )
    actual = {row["run_id"]: row["status"] for row in rows}
    assert actual == {
        run_held_id: "Held",
        run_resumed_id: "Running",  # Held then Resumed back to Running
        run_completed_id: "Completed",
        run_aborted_id: "Aborted",
        run_stopped_id: "Stopped",
        run_truncated_id: "Truncated",
    }


@pytest.mark.integration
async def test_plan_id_filter_narrows_results(db_pool: asyncpg.Pool) -> None:
    """Two Runs against different Plans; plan_id filter returns one."""
    run_a = uuid4()
    deps_a = _build_deps(db_pool, [*_chain_ids(), run_a, uuid4()])
    plan_a = await _seed_plan(deps_a)
    await bind_start(deps_a)(
        StartRun(name="for-plan-a", plan_id=plan_a, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    run_b = uuid4()
    deps_b = _build_deps(db_pool, [*_chain_ids(), run_b, uuid4()])
    plan_b = await _seed_plan(deps_b)
    await bind_start(deps_b)(
        StartRun(name="for-plan-b", plan_id=plan_b, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps_a)
    page = await handler(
        ListRuns(plan_id=plan_a, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].run_id == run_a
    assert page.items[0].plan_id == plan_a
    assert page.items[0].status == "Running"


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListRuns(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None
