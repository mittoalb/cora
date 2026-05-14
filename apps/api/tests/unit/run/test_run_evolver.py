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
from cora.run.aggregates.run.events import (
    RunAborted,
    RunCompleted,
    RunHeld,
    RunResumed,
    RunStarted,
    RunStopped,
    RunTruncated,
)

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


# ---------- 6f-3: Held / Resumed / Stopped ----------


@pytest.mark.unit
def test_evolve_run_held_transitions_to_held_preserving_other_fields() -> None:
    started = _run_started()
    state = evolve(None, started)
    held = evolve(state, RunHeld(run_id=started.run_id, occurred_at=_NOW))
    assert held == replace(state, status=RunStatus.HELD)
    assert held.status is RunStatus.HELD


@pytest.mark.unit
def test_evolve_run_resumed_transitions_held_back_to_running() -> None:
    started = _run_started()
    running = evolve(None, started)
    held = evolve(running, RunHeld(run_id=started.run_id, occurred_at=_NOW))
    resumed = evolve(held, RunResumed(run_id=started.run_id, occurred_at=_NOW))
    assert resumed.status is RunStatus.RUNNING
    # The Run identity / plan / subject survive the round trip.
    assert resumed == replace(held, status=RunStatus.RUNNING)


@pytest.mark.unit
def test_evolve_run_stopped_transitions_to_stopped_preserving_other_fields() -> None:
    started = _run_started()
    state = evolve(None, started)
    stopped = evolve(
        state,
        RunStopped(run_id=started.run_id, reason="hit time budget", occurred_at=_NOW),
    )
    assert stopped == replace(state, status=RunStatus.STOPPED)
    assert stopped.status is RunStatus.STOPPED


@pytest.mark.unit
def test_evolve_run_held_on_none_state_raises() -> None:
    with pytest.raises(ValueError, match="RunHeld before RunStarted"):
        evolve(None, RunHeld(run_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_run_resumed_on_none_state_raises() -> None:
    with pytest.raises(ValueError, match="RunResumed before RunStarted"):
        evolve(None, RunResumed(run_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_evolve_run_stopped_on_none_state_raises() -> None:
    with pytest.raises(ValueError, match="RunStopped before RunStarted"):
        evolve(None, RunStopped(run_id=uuid4(), reason="X", occurred_at=_NOW))


@pytest.mark.unit
def test_fold_multi_cycle_hold_resume_then_complete_yields_completed() -> None:
    """Hold ⇄ Resume is unlimited-cycle. After [held, resumed, held,
    resumed, completed] the fold lands in Completed. Per-cycle audit
    lives in the event stream itself."""
    run_id = uuid4()
    started = _run_started(run_id=run_id)
    state = fold(
        [
            started,
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunResumed(run_id=run_id, occurred_at=_NOW),
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunResumed(run_id=run_id, occurred_at=_NOW),
            RunCompleted(run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is RunStatus.COMPLETED


@pytest.mark.unit
def test_fold_started_then_held_then_aborted_yields_aborted() -> None:
    """6f-3 widens abort source set to Running | Held: Held → Aborted folds correctly."""
    run_id = uuid4()
    started = _run_started(run_id=run_id)
    state = fold(
        [
            started,
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunAborted(run_id=run_id, reason="emergency during hold", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is RunStatus.ABORTED


@pytest.mark.unit
def test_fold_started_then_held_then_stopped_yields_stopped() -> None:
    """stop_run accepts Held source: Held → Stopped folds correctly."""
    run_id = uuid4()
    started = _run_started(run_id=run_id)
    state = fold(
        [
            started,
            RunHeld(run_id=run_id, occurred_at=_NOW),
            RunStopped(run_id=run_id, reason="ending early during hold", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is RunStatus.STOPPED


# ---------- 7d: raid preservation across transitions ----------


@pytest.mark.unit
def test_evolve_run_started_preserves_raid() -> None:
    """7d retrofit: raid carried verbatim into Run state on RunStarted."""
    state = evolve(
        None,
        _run_started_with_raid(raid="https://raid.org/10.7935/cora-test"),
    )
    assert state.raid == "https://raid.org/10.7935/cora-test"


@pytest.mark.unit
def test_evolve_run_started_without_raid_yields_state_with_raid_none() -> None:
    """raid is optional; pre-7d-style RunStarted folds with raid=None."""
    state = evolve(None, _run_started())
    assert state.raid is None


# ---------- 6g-c additive RunStarted payload (overrides + effective + triggered_by) ----------


@pytest.mark.unit
def test_evolve_run_started_folds_6gc_parameter_fields() -> None:
    """6g-c additive payload: parameter_overrides + effective_parameters
    + triggered_by carry verbatim from RunStarted into Run state."""
    overrides = {"energy_kev": 12.0}
    effective = {"energy_kev": 12.0, "exposure_ms": 100}
    state = evolve(
        None,
        RunStarted(
            run_id=uuid4(),
            name="X",
            plan_id=uuid4(),
            subject_id=None,
            occurred_at=_NOW,
            parameter_overrides=overrides,
            effective_parameters=effective,
            triggered_by="operator:opid:5",
        ),
    )
    assert state.parameter_overrides == overrides
    assert state.effective_parameters == effective
    assert state.triggered_by == "operator:opid:5"


@pytest.mark.unit
def test_evolve_run_started_without_6gc_fields_yields_state_defaults() -> None:
    """Pre-6g-c-style RunStarted (defaults via additive-state pattern)
    folds with empty dicts and None triggered_by."""
    state = evolve(None, _run_started())
    assert state.parameter_overrides == {}
    assert state.effective_parameters == {}
    assert state.triggered_by is None


@pytest.mark.unit
def test_evolve_held_then_resumed_preserves_6gc_fields() -> None:
    """Critical pin: every transition uses dataclass.replace which
    preserves all fields. parameter_overrides + effective_parameters
    + triggered_by must survive Hold → Resume cycles unchanged."""
    overrides = {"energy_kev": 12.0}
    effective = {"energy_kev": 12.0, "exposure_ms": 100}
    state = evolve(
        None,
        RunStarted(
            run_id=uuid4(),
            name="X",
            plan_id=uuid4(),
            subject_id=None,
            occurred_at=_NOW,
            parameter_overrides=overrides,
            effective_parameters=effective,
            triggered_by="scheduler:auto",
        ),
    )
    held = evolve(state, RunHeld(run_id=state.id, occurred_at=_NOW))
    resumed = evolve(held, RunResumed(run_id=state.id, occurred_at=_NOW))
    assert resumed.parameter_overrides == overrides
    assert resumed.effective_parameters == effective
    assert resumed.triggered_by == "scheduler:auto"
    assert resumed.status is RunStatus.RUNNING


@pytest.mark.unit
@pytest.mark.parametrize(
    "transitions",
    [
        [RunHeld],
        [RunHeld, RunResumed],
        [RunCompleted],
        [RunAborted],
        [RunStopped],
        [RunTruncated],
        [RunHeld, RunAborted],
        [RunHeld, RunStopped],
        [RunHeld, RunTruncated],
        [RunHeld, RunResumed, RunCompleted],
    ],
)
def test_fold_preserves_raid_across_every_transition_path(
    transitions: list[type],
) -> None:
    """Structural property: replace(state, status=...) in evolver
    transition arms preserves the raid field by dataclass semantics.
    A future evolver refactor that constructs Run() from scratch in
    a transition arm would silently drop raid; this test guards it.

    Covers every reachable terminal (Completed / Aborted / Stopped /
    Truncated) plus the bidirectional Hold cycle, from the genesis
    raid being set on RunStarted.
    """
    run_id = uuid4()
    raid_value = "https://raid.org/10.7935/cora-fold-test"
    events: list[object] = [_run_started_with_raid(run_id=run_id, raid=raid_value)]
    for cls in transitions:
        if cls is RunAborted or cls is RunStopped:
            events.append(cls(run_id=run_id, reason="X", occurred_at=_NOW))
        elif cls is RunTruncated:
            events.append(
                RunTruncated(
                    run_id=run_id,
                    reason="X",
                    interrupted_at=None,
                    occurred_at=_NOW,
                )
            )
        else:
            events.append(cls(run_id=run_id, occurred_at=_NOW))
    state = fold(events)  # type: ignore[arg-type]
    assert state is not None
    assert state.raid == raid_value


def _run_started_with_raid(
    *,
    run_id: UUID | None = None,
    raid: str | None,
) -> RunStarted:
    return RunStarted(
        run_id=run_id or uuid4(),
        name="32-ID FlyScan",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        raid=raid,
    )
