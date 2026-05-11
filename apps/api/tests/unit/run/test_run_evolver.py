"""Unit tests for the Run aggregate's evolver."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.run.aggregates.run import (
    Run,
    RunName,
    RunStatus,
    evolve,
    fold,
)
from cora.run.aggregates.run.events import RunAborted, RunCompleted, RunStarted

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _run_started(
    *,
    run_id: UUID | None = None,
    plan_id: UUID | None = None,
    subject_id: UUID | None = None,
) -> RunStarted:
    """Test helper: RunStarted with sensible defaults."""
    return RunStarted(
        run_id=run_id or uuid4(),
        name="32-ID FlyScan",
        plan_id=plan_id or uuid4(),
        subject_id=subject_id,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_evolve_run_started_sets_status_to_running_with_subject() -> None:
    """RunStarted is the genesis event; status=Running, all fields preserved."""
    run_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    state = evolve(
        None,
        RunStarted(
            run_id=run_id,
            name="32-ID FlyScan",
            plan_id=plan_id,
            subject_id=subject_id,
            occurred_at=_NOW,
        ),
    )
    assert state == Run(
        id=run_id,
        name=RunName("32-ID FlyScan"),
        plan_id=plan_id,
        subject_id=subject_id,
        status=RunStatus.RUNNING,
    )


@pytest.mark.unit
def test_evolve_run_started_without_subject_sets_subject_id_to_none() -> None:
    """Calibration / dark-field runs fold with subject_id=None."""
    state = evolve(None, _run_started(subject_id=None))
    assert state.subject_id is None
    assert state.status is RunStatus.RUNNING


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_run_started_returns_run() -> None:
    run_id = uuid4()
    state = fold([_run_started(run_id=run_id)])
    assert state is not None
    assert state.id == run_id
    assert state.status is RunStatus.RUNNING


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    events = [_run_started()]
    assert fold(events) == fold(events)


# ---------- 6f-2: terminal transitions ----------


@pytest.mark.unit
def test_evolve_run_completed_transitions_to_completed_preserving_other_fields() -> None:
    started = _run_started()
    state = evolve(None, started)
    completed = evolve(state, RunCompleted(run_id=started.run_id, occurred_at=_NOW))
    assert completed == replace(state, status=RunStatus.COMPLETED)
    assert completed.status is RunStatus.COMPLETED


@pytest.mark.unit
def test_evolve_run_aborted_transitions_to_aborted_preserving_other_fields() -> None:
    started = _run_started()
    state = evolve(None, started)
    aborted = evolve(
        state,
        RunAborted(run_id=started.run_id, reason="detector overheating", occurred_at=_NOW),
    )
    assert aborted == replace(state, status=RunStatus.ABORTED)
    assert aborted.status is RunStatus.ABORTED


@pytest.mark.unit
def test_evolve_run_completed_on_none_state_raises() -> None:
    """Defensive guard: a transition event before a genesis means
    the stream is contaminated. Fail loud rather than silently fold."""
    with pytest.raises(ValueError, match="RunCompleted before RunStarted"):
        evolve(None, RunCompleted(run_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_run_aborted_on_none_state_raises() -> None:
    with pytest.raises(ValueError, match="RunAborted before RunStarted"):
        evolve(None, RunAborted(run_id=uuid4(), reason="X", occurred_at=_NOW))


@pytest.mark.unit
def test_fold_started_then_completed_yields_completed() -> None:
    started = _run_started()
    state = fold([started, RunCompleted(run_id=started.run_id, occurred_at=_NOW)])
    assert state is not None
    assert state.status is RunStatus.COMPLETED


@pytest.mark.unit
def test_fold_started_then_aborted_yields_aborted_and_preserves_run_fields() -> None:
    run_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    started = _run_started(run_id=run_id, plan_id=plan_id, subject_id=subject_id)
    state = fold([started, RunAborted(run_id=run_id, reason="beam dump", occurred_at=_NOW)])
    assert state is not None
    assert state.id == run_id
    assert state.plan_id == plan_id
    assert state.subject_id == subject_id
    assert state.status is RunStatus.ABORTED
