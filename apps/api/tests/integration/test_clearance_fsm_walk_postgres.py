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
    ClearanceStatus,
    RunBinding,
    load_clearance,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import (
    activate_clearance,
    append_clearance_review_step,
    approve_clearance,
    register_clearance,
    reject_clearance,
    start_clearance_review,
    submit_clearance,
)
from cora.safety.features.activate_clearance import ActivateClearance
from cora.safety.features.append_clearance_review_step import AppendClearanceReviewStep
from cora.safety.features.approve_clearance import ApproveClearance
from cora.safety.features.register_clearance import RegisterClearance
from cora.safety.features.reject_clearance import RejectClearance
from cora.safety.features.start_clearance_review import StartClearanceReview
from cora.safety.features.submit_clearance import SubmitClearance
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FACILITY_CODE = "cora"
_ESAF_TEMPLATE_ID: ClearanceTemplateId = ClearanceTemplateId(
    clearance_template_stream_id(_FACILITY_CODE, "ESAF")
)


@pytest.mark.integration
async def test_full_fsm_walk_to_active_postgres(db_pool: asyncpg.Pool) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    # Seed the in-memory ClearanceTemplateLookup with an Active "ESAF"
    # template in the "cora" facility so register_clearance's handler
    # cross-aggregate template lookup resolves before the decider runs.
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=_ESAF_TEMPLATE_ID,
        facility_code=_FACILITY_CODE,
        code="ESAF",
        status="Active",
        version=1,
    )
    rid = uuid4()

    cid = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=_ESAF_TEMPLATE_ID,
            facility_code=_FACILITY_CODE,
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
    await start_clearance_review.bind(deps)(
        StartClearanceReview(clearance_id=cid, first_reviewer_role="BeamlineScientist"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_clearance(deps.event_store, cid)
    assert state is not None
    assert state.status == ClearanceStatus.UNDER_REVIEW

    # Append one Approved review step
    await append_clearance_review_step.bind(deps)(
        AppendClearanceReviewStep(
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
    assert len(state.review_steps) == 1
    assert state.review_steps[0].decision == "Approved"

    # UnderReview -> Approved
    await approve_clearance.bind(deps)(
        ApproveClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_clearance(deps.event_store, cid)
    assert state is not None
    assert state.status == ClearanceStatus.APPROVED

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
    assert state.facility_code.value == _FACILITY_CODE
    assert state.template_id == _ESAF_TEMPLATE_ID


@pytest.mark.integration
async def test_full_fsm_walk_to_rejected_postgres(db_pool: asyncpg.Pool) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(10)])
    # Seed the in-memory ClearanceTemplateLookup with an Active "ESAF"
    # template in the "cora" facility so register_clearance's handler
    # cross-aggregate template lookup resolves before the decider runs.
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=_ESAF_TEMPLATE_ID,
        facility_code=_FACILITY_CODE,
        code="ESAF",
        status="Active",
        version=1,
    )

    cid = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=_ESAF_TEMPLATE_ID,
            facility_code=_FACILITY_CODE,
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
    await start_clearance_review.bind(deps)(
        StartClearanceReview(clearance_id=cid, first_reviewer_role="ESH"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await reject_clearance.bind(deps)(
        RejectClearance(
            clearance_id=cid,
            reason="ESRB found insufficient PPE specification",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    state = await load_clearance(deps.event_store, cid)
    assert state is not None
    assert state.status == ClearanceStatus.REJECTED
