"""End-to-end integration test: full Clearance FSM walk against real Postgres.

Walks `Defined -> Submitted -> UnderReview -> Approved -> Active`
through every transition handler against a live PG event store and
verifies (via load_clearance) that fold reconstructs the expected
state at each step.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.safety.aggregates.clearance import (
    ClearanceKind,
    ClearanceStatus,
    RunBinding,
    load_clearance,
)
from cora.safety.features import (
    activate_clearance,
    approve_clearance,
    begin_review_clearance,
    record_review_step_clearance,
    register_clearance,
    reject_clearance,
    submit_clearance,
)
from cora.safety.features.activate_clearance import ActivateClearance
from cora.safety.features.approve_clearance import ApproveClearance
from cora.safety.features.begin_review_clearance import BeginReviewClearance
from cora.safety.features.record_review_step_clearance import RecordReviewStepClearance
from cora.safety.features.register_clearance import RegisterClearance
from cora.safety.features.reject_clearance import RejectClearance
from cora.safety.features.submit_clearance import SubmitClearance
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_full_fsm_walk_to_active_postgres(db_pool: asyncpg.Pool) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    rid = uuid4()
    fid = uuid4()

    cid = await register_clearance.bind(deps)(
        RegisterClearance(
            kind=ClearanceKind.ESAF,
            facility_asset_id=fid,
            title="Pilot",
            bindings=frozenset({RunBinding(run_id=rid)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Defined -> Submitted
    await submit_clearance.bind(deps)(
        SubmitClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_clearance(deps.event_store, cid)
    assert state is not None
    assert state.status == ClearanceStatus.SUBMITTED

    # Submitted -> UnderReview
    await begin_review_clearance.bind(deps)(
        BeginReviewClearance(clearance_id=cid, first_reviewer_role="BeamlineScientist"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_clearance(deps.event_store, cid)
    assert state is not None
    assert state.status == ClearanceStatus.UNDER_REVIEW

    # Append one Approved review step
    await record_review_step_clearance.bind(deps)(
        RecordReviewStepClearance(
            clearance_id=cid,
            step_index=0,
            role="BeamlineScientist",
            actor_id=_PRINCIPAL_ID,
            decision="Approved",
            decided_at=_NOW,
            notes="LGTM",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_clearance(deps.event_store, cid)
    assert state is not None
    assert state.status == ClearanceStatus.UNDER_REVIEW
    assert len(state.reviewers) == 1
    assert state.reviewers[0].decision == "Approved"

    # UnderReview -> Approved
    approving_actor = uuid4()
    await approve_clearance.bind(deps)(
        ApproveClearance(clearance_id=cid, approving_actor_id=approving_actor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_clearance(deps.event_store, cid)
    assert state is not None
    assert state.status == ClearanceStatus.APPROVED
    assert state.last_reviewed_by_actor_id == approving_actor

    # Approved -> Active
    await activate_clearance.bind(deps)(
        ActivateClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_clearance(deps.event_store, cid)
    assert state is not None
    assert state.status == ClearanceStatus.ACTIVE
    # Identity + facility preserved across the full FSM walk
    assert state.facility_asset_id == fid
    assert state.kind == ClearanceKind.ESAF


@pytest.mark.integration
async def test_full_fsm_walk_to_rejected_postgres(db_pool: asyncpg.Pool) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(10)])

    cid = await register_clearance.bind(deps)(
        RegisterClearance(
            kind=ClearanceKind.ESAF,
            facility_asset_id=uuid4(),
            title="Pilot",
            bindings=frozenset({RunBinding(run_id=uuid4())}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await submit_clearance.bind(deps)(
        SubmitClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await begin_review_clearance.bind(deps)(
        BeginReviewClearance(clearance_id=cid, first_reviewer_role="ESH"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rejecting_actor = uuid4()
    await reject_clearance.bind(deps)(
        RejectClearance(
            clearance_id=cid,
            rejecting_actor_id=rejecting_actor,
            reason="ESRB found insufficient PPE specification",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_clearance(deps.event_store, cid)
    assert state is not None
    assert state.status == ClearanceStatus.REJECTED
    assert state.last_reviewed_by_actor_id == rejecting_actor
