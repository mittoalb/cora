"""Unit tests for the Run aggregate's evolver."""

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
from cora.run.aggregates.run.events import RunStarted

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
def test_evolve_run_started_sets_status_to_started_with_subject() -> None:
    """RunStarted is the genesis event; status=Started, all fields preserved."""
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
        status=RunStatus.STARTED,
    )


@pytest.mark.unit
def test_evolve_run_started_without_subject_sets_subject_id_to_none() -> None:
    """Calibration / dark-field runs fold with subject_id=None."""
    state = evolve(None, _run_started(subject_id=None))
    assert state.subject_id is None
    assert state.status is RunStatus.STARTED


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_run_started_returns_run() -> None:
    run_id = uuid4()
    state = fold([_run_started(run_id=run_id)])
    assert state is not None
    assert state.id == run_id
    assert state.status is RunStatus.STARTED


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    events = [_run_started()]
    assert fold(events) == fold(events)
