"""Evolver / fold tests: replay determinism + last_status_reason preservation."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from cora.trust.aggregates.visit import (
    Visit,
    VisitAborted,
    VisitArrived,
    VisitCancelled,
    VisitCompleted,
    VisitEvent,
    VisitHeld,
    VisitRegistered,
    VisitResumed,
    VisitStarted,
    VisitStatus,
    VisitType,
    VisitVoided,
    evolve,
    fold,
)

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_VID = UUID("01900000-0000-7000-8000-00000000c001")
_PID = UUID("01900000-0000-7000-8000-00000000c002")
_SID = UUID("01900000-0000-7000-8000-00000000c003")


def _registered() -> VisitRegistered:
    return VisitRegistered(
        visit_id=_VID,
        policy_id=_PID,
        surface_id=_SID,
        type=VisitType.USER.value,
        planned_start_at=_NOW,
        planned_end_at=_NOW + timedelta(hours=4),
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_fold_empty_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_genesis_only_yields_planned_state() -> None:
    state = fold([_registered()])
    assert state is not None
    assert state.id == _VID
    assert state.policy_id == _PID
    assert state.surface_id == _SID
    assert state.type == VisitType.USER
    assert state.status == VisitStatus.PLANNED


@pytest.mark.unit
def test_full_lifecycle_walks_through_all_8_states() -> None:
    """Cover Planned -> Arrived -> InProgress <-> OnHold -> Completed.
    +Cancel and +Abort and +Void share the terminal-transition path
    tested separately below."""
    state = fold(
        [
            _registered(),
            VisitArrived(visit_id=_VID, occurred_at=_NOW),
            VisitStarted(visit_id=_VID, occurred_at=_NOW),
            VisitHeld(visit_id=_VID, reason="beam dump", occurred_at=_NOW),
            VisitResumed(visit_id=_VID, occurred_at=_NOW),
            VisitCompleted(visit_id=_VID, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status == VisitStatus.COMPLETED


@pytest.mark.unit
def test_resume_preserves_last_status_reason_audit_breadcrumb() -> None:
    """Per [[project_visit_aggregate_design]] lock: Resume does NOT clear
    last_status_reason; the prior Hold's reason stays readable for audit."""
    state = fold(
        [
            _registered(),
            VisitArrived(visit_id=_VID, occurred_at=_NOW),
            VisitStarted(visit_id=_VID, occurred_at=_NOW),
            VisitHeld(visit_id=_VID, reason="beam dump", occurred_at=_NOW),
            VisitResumed(visit_id=_VID, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status == VisitStatus.IN_PROGRESS
    assert state.last_status_reason == "beam dump"


@pytest.mark.parametrize(
    ("terminal_event", "expected_status", "expected_reason"),
    [
        (VisitCompleted(visit_id=_VID, occurred_at=_NOW), VisitStatus.COMPLETED, None),
        (
            VisitCancelled(visit_id=_VID, reason="no-show", occurred_at=_NOW),
            VisitStatus.CANCELLED,
            "no-show",
        ),
        (
            VisitAborted(visit_id=_VID, reason="equipment fault", occurred_at=_NOW),
            VisitStatus.ABORTED,
            "equipment fault",
        ),
        (
            VisitVoided(visit_id=_VID, reason="duplicate", occurred_at=_NOW),
            VisitStatus.VOIDED,
            "duplicate",
        ),
    ],
)
@pytest.mark.unit
def test_all_4_terminators_produce_correct_status_and_reason(
    terminal_event: VisitEvent, expected_status: VisitStatus, expected_reason: str | None
) -> None:
    base: list[VisitEvent] = [
        _registered(),
        VisitArrived(visit_id=_VID, occurred_at=_NOW),
        VisitStarted(visit_id=_VID, occurred_at=_NOW),
    ]
    state = fold([*base, terminal_event])
    assert state is not None
    assert state.status == expected_status
    if expected_reason is None:
        # Completed does not carry a reason; last_status_reason stays None.
        assert state.last_status_reason is None
    else:
        assert state.last_status_reason == expected_reason


@pytest.mark.unit
def test_evolve_replay_is_deterministic() -> None:
    """Same event sequence produces equal Visit instances (frozen dataclass)."""
    events: list[VisitEvent] = [
        _registered(),
        VisitArrived(visit_id=_VID, occurred_at=_NOW),
        VisitStarted(visit_id=_VID, occurred_at=_NOW),
    ]
    first = fold(events)
    second = fold(events)
    assert first == second


@pytest.mark.unit
def test_evolve_step_by_step_matches_fold() -> None:
    events: list[VisitEvent] = [
        _registered(),
        VisitArrived(visit_id=_VID, occurred_at=_NOW),
        VisitStarted(visit_id=_VID, occurred_at=_NOW),
        VisitHeld(visit_id=_VID, reason="r", occurred_at=_NOW),
    ]
    fold_state = fold(events)

    incremental: Visit | None = None
    for e in events:
        incremental = evolve(incremental, e)

    assert incremental == fold_state
