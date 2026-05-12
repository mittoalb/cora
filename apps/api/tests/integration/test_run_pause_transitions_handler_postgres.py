"""End-to-end integration tests: 6f-3 transitions against real Postgres.

Two coverage scenarios mirroring the 6f-2 transitions test:
  - **Multi-cycle hold/resume/stop**: full upstream chain + start +
    [hold, resume, hold, resume, stop] + load_run returns the
    Stopped state, with the persisted RunStopped carrying the
    trimmed reason and the event stream preserving cycle order.
  - **Held-source abort**: full upstream chain + start + hold +
    abort + load_run returns the Aborted state, exercising the
    6f-3 widening of abort's source set to include Held.

Each test uses a distinct run_id (different aggregate stream) so
they don't interfere even if the test DB is shared.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

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
from cora.recipe.features import (
    define_method,
    define_plan,
    define_practice,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.aggregates.run import RunStatus, load_run
from cora.run.features import abort_run, hold_run, resume_run, start_run, stop_run
from cora.run.features.abort_run import AbortRun
from cora.run.features.hold_run import HoldRun
from cora.run.features.resume_run import ResumeRun
from cora.run.features.start_run import StartRun
from cora.run.features.stop_run import StopRun
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps_with_ids(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator(ids),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )


async def _seed_chain_and_start_run(
    deps: Kernel,
    *,
    asset_id: UUID,
    cap_id: UUID,
    method_id: UUID,
    practice_id: UUID,
    site_id: UUID,
    subject_id: UUID,
    plan_id: UUID,
    run_id: UUID,
) -> None:
    await define_capability.bind(deps)(
        DefineCapability(name="FlyMotion"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(name="EigerDetector", level=AssetLevel.ENTERPRISE, parent_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_capability.bind(deps)(
        AddAssetCapability(asset_id=asset_id, capability_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_method.bind(deps)(
        DefineMethod(name="XRF Fly Scan", needs_capabilities=frozenset({cap_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_practice.bind(deps)(
        DefinePractice(name="APS XRF", method_id=method_id, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_plan.bind(deps)(
        DefinePlan(
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_subject.bind(deps)(
        RegisterSubject(name="PorousCeramicSample-A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned_id = await start_run.bind(deps)(
        StartRun(
            name="32-ID FlyScan morning session",
            plan_id=plan_id,
            subject_id=subject_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == run_id


@pytest.mark.integration
async def test_multi_cycle_hold_resume_then_stop_persists_full_event_stream(
    db_pool: asyncpg.Pool,
) -> None:
    """Multi-cycle hold/resume sequence then a controlled stop. The
    persisted event stream preserves cycle order; the fold lands at
    Stopped with the trimmed reason."""
    cap_id = UUID("01900000-0000-7000-8000-00000066aa01")
    cap_event_id = UUID("01900000-0000-7000-8000-00000066aa02")
    asset_id = UUID("01900000-0000-7000-8000-00000066ab01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-00000066ab02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-00000066ab03")
    method_id = UUID("01900000-0000-7000-8000-00000066ac01")
    method_event_id = UUID("01900000-0000-7000-8000-00000066ac02")
    practice_id = UUID("01900000-0000-7000-8000-00000066ad01")
    practice_event_id = UUID("01900000-0000-7000-8000-00000066ad02")
    site_id = UUID("01900000-0000-7000-8000-00000066ae01")
    plan_id = UUID("01900000-0000-7000-8000-00000066af01")
    plan_event_id = UUID("01900000-0000-7000-8000-00000066af02")
    subject_id = UUID("01900000-0000-7000-8000-00000066b001")
    subject_register_event_id = UUID("01900000-0000-7000-8000-00000066b002")
    subject_mount_event_id = UUID("01900000-0000-7000-8000-00000066b003")
    run_id = UUID("01900000-0000-7000-8000-00000066b101")
    run_started_event_id = UUID("01900000-0000-7000-8000-00000066b102")
    held_1_event_id = UUID("01900000-0000-7000-8000-00000066b103")
    resumed_1_event_id = UUID("01900000-0000-7000-8000-00000066b104")
    held_2_event_id = UUID("01900000-0000-7000-8000-00000066b105")
    resumed_2_event_id = UUID("01900000-0000-7000-8000-00000066b106")
    stopped_event_id = UUID("01900000-0000-7000-8000-00000066b107")

    deps = _build_deps_with_ids(
        db_pool,
        [
            cap_id,
            cap_event_id,
            asset_id,
            asset_register_event_id,
            asset_addcap_event_id,
            method_id,
            method_event_id,
            practice_id,
            practice_event_id,
            plan_id,
            plan_event_id,
            subject_id,
            subject_register_event_id,
            subject_mount_event_id,
            run_id,
            run_started_event_id,
            held_1_event_id,
            resumed_1_event_id,
            held_2_event_id,
            resumed_2_event_id,
            stopped_event_id,
        ],
    )

    await _seed_chain_and_start_run(
        deps,
        asset_id=asset_id,
        cap_id=cap_id,
        method_id=method_id,
        practice_id=practice_id,
        site_id=site_id,
        subject_id=subject_id,
        plan_id=plan_id,
        run_id=run_id,
    )

    # Hold ⇄ Resume cycle (twice) then Stop.
    await hold_run.bind(deps)(
        HoldRun(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await resume_run.bind(deps)(
        ResumeRun(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await hold_run.bind(deps)(
        HoldRun(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await resume_run.bind(deps)(
        ResumeRun(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await stop_run.bind(deps)(
        StopRun(run_id=run_id, reason="  hit time budget cleanly  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, stream_version = await deps.event_store.load("Run", run_id)
    assert stream_version == 6
    assert [e.event_type for e in events] == [
        "RunStarted",
        "RunHeld",
        "RunResumed",
        "RunHeld",
        "RunResumed",
        "RunStopped",
    ]
    stopped = events[5]
    assert stopped.event_id == stopped_event_id
    assert stopped.metadata == {"command": "StopRun"}
    assert stopped.payload == {
        "run_id": str(run_id),
        "reason": "hit time budget cleanly",
        "occurred_at": _NOW.isoformat(),
    }

    state = await load_run(deps.event_store, run_id)
    assert state is not None
    assert state.id == run_id
    assert state.plan_id == plan_id
    assert state.subject_id == subject_id
    assert state.status is RunStatus.STOPPED


@pytest.mark.integration
async def test_abort_from_held_state_persists_and_round_trips_to_aborted(
    db_pool: asyncpg.Pool,
) -> None:
    """6f-3 widens abort source set to include Held. Hold + Abort
    yields Aborted without an intervening Resume."""
    cap_id = UUID("01900000-0000-7000-8000-00000067aa01")
    cap_event_id = UUID("01900000-0000-7000-8000-00000067aa02")
    asset_id = UUID("01900000-0000-7000-8000-00000067ab01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-00000067ab02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-00000067ab03")
    method_id = UUID("01900000-0000-7000-8000-00000067ac01")
    method_event_id = UUID("01900000-0000-7000-8000-00000067ac02")
    practice_id = UUID("01900000-0000-7000-8000-00000067ad01")
    practice_event_id = UUID("01900000-0000-7000-8000-00000067ad02")
    site_id = UUID("01900000-0000-7000-8000-00000067ae01")
    plan_id = UUID("01900000-0000-7000-8000-00000067af01")
    plan_event_id = UUID("01900000-0000-7000-8000-00000067af02")
    subject_id = UUID("01900000-0000-7000-8000-00000067b001")
    subject_register_event_id = UUID("01900000-0000-7000-8000-00000067b002")
    subject_mount_event_id = UUID("01900000-0000-7000-8000-00000067b003")
    run_id = UUID("01900000-0000-7000-8000-00000067b101")
    run_started_event_id = UUID("01900000-0000-7000-8000-00000067b102")
    held_event_id = UUID("01900000-0000-7000-8000-00000067b103")
    aborted_event_id = UUID("01900000-0000-7000-8000-00000067b104")

    deps = _build_deps_with_ids(
        db_pool,
        [
            cap_id,
            cap_event_id,
            asset_id,
            asset_register_event_id,
            asset_addcap_event_id,
            method_id,
            method_event_id,
            practice_id,
            practice_event_id,
            plan_id,
            plan_event_id,
            subject_id,
            subject_register_event_id,
            subject_mount_event_id,
            run_id,
            run_started_event_id,
            held_event_id,
            aborted_event_id,
        ],
    )

    await _seed_chain_and_start_run(
        deps,
        asset_id=asset_id,
        cap_id=cap_id,
        method_id=method_id,
        practice_id=practice_id,
        site_id=site_id,
        subject_id=subject_id,
        plan_id=plan_id,
        run_id=run_id,
    )

    await hold_run.bind(deps)(
        HoldRun(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await abort_run.bind(deps)(
        AbortRun(run_id=run_id, reason="emergency during hold"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, stream_version = await deps.event_store.load("Run", run_id)
    assert stream_version == 3
    assert [e.event_type for e in events] == [
        "RunStarted",
        "RunHeld",
        "RunAborted",
    ]
    aborted = events[2]
    assert aborted.event_id == aborted_event_id
    assert aborted.payload["reason"] == "emergency during hold"

    state = await load_run(deps.event_store, run_id)
    assert state is not None
    assert state.status is RunStatus.ABORTED
