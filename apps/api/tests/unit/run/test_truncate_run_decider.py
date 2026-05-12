"""Unit tests for the `truncate_run` slice's pure decider.

Multi-source partial-data terminal: `Running | Held -> Truncated`.
Truncating any terminal raises (strict-not-idempotent for Truncated).
`reason` validated via the `RunTruncateReason` VO. `interrupted_at`
is optional; if set, must not be in the future.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    InvalidRunInterruptedAtError,
    InvalidRunTruncateReasonError,
    Run,
    RunCannotTruncateError,
    RunName,
    RunNotFoundError,
    RunStatus,
    RunTruncated,
)
from cora.run.features import truncate_run
from cora.run.features.truncate_run import TruncateRun

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_INTERRUPTED_AT = datetime(2026, 5, 9, 3, 14, 7, tzinfo=UTC)


def _run(*, status: RunStatus = RunStatus.RUNNING) -> Run:
    return Run(
        id=uuid4(),
        name=RunName("32-ID FlyScan"),
        plan_id=uuid4(),
        subject_id=uuid4(),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_run_truncated_for_running_state() -> None:
    state = _run(status=RunStatus.RUNNING)
    events = truncate_run.decide(
        state=state,
        command=TruncateRun(
            run_id=state.id,
            reason="power loss to beamline 32-ID at ~03:14 UTC",
            interrupted_at=_INTERRUPTED_AT,
        ),
        now=_NOW,
    )
    assert events == [
        RunTruncated(
            run_id=state.id,
            reason="power loss to beamline 32-ID at ~03:14 UTC",
            interrupted_at=_INTERRUPTED_AT,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_accepts_held_source_state() -> None:
    """Multi-source guard: truncate_run accepts both Running and Held."""
    state = _run(status=RunStatus.HELD)
    events = truncate_run.decide(
        state=state,
        command=TruncateRun(
            run_id=state.id,
            reason="held when interrupt happened",
            interrupted_at=None,
        ),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].reason == "held when interrupt happened"


@pytest.mark.unit
def test_decide_accepts_null_interrupted_at() -> None:
    """interrupted_at is optional; None is the unknown / not-supplied case."""
    state = _run()
    events = truncate_run.decide(
        state=state,
        command=TruncateRun(
            run_id=state.id,
            reason="found dangling Run Monday morning",
            interrupted_at=None,
        ),
        now=_NOW,
    )
    assert events[0].interrupted_at is None


@pytest.mark.unit
def test_decide_trims_reason_via_value_object() -> None:
    state = _run()
    events = truncate_run.decide(
        state=state,
        command=TruncateRun(
            run_id=state.id,
            reason="  weekend power outage; data captured to projection 487  ",
            interrupted_at=_INTERRUPTED_AT,
        ),
        now=_NOW,
    )
    assert events[0].reason == "weekend power outage; data captured to projection 487"


@pytest.mark.unit
def test_decide_raises_run_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(RunNotFoundError) as exc_info:
        truncate_run.decide(
            state=None,
            command=TruncateRun(run_id=target_id, reason="X", interrupted_at=None),
            now=_NOW,
        )
    assert exc_info.value.run_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_whitespace_only() -> None:
    state = _run()
    with pytest.raises(InvalidRunTruncateReasonError):
        truncate_run.decide(
            state=state,
            command=TruncateRun(run_id=state.id, reason="   ", interrupted_at=None),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_too_long() -> None:
    state = _run()
    with pytest.raises(InvalidRunTruncateReasonError):
        truncate_run.decide(
            state=state,
            command=TruncateRun(run_id=state.id, reason="a" * 501, interrupted_at=None),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_interrupted_at_for_future_value() -> None:
    """interrupted_at after now is invalid; cannot be interrupted in the future."""
    state = _run()
    future = _NOW + timedelta(seconds=1)
    with pytest.raises(InvalidRunInterruptedAtError) as exc_info:
        truncate_run.decide(
            state=state,
            command=TruncateRun(run_id=state.id, reason="X", interrupted_at=future),
            now=_NOW,
        )
    assert exc_info.value.interrupted_at == future
    assert exc_info.value.now == _NOW


@pytest.mark.unit
def test_decide_accepts_interrupted_at_equal_to_now() -> None:
    """interrupted_at == now is the boundary; should be accepted."""
    state = _run()
    events = truncate_run.decide(
        state=state,
        command=TruncateRun(run_id=state.id, reason="just-now interruption", interrupted_at=_NOW),
        now=_NOW,
    )
    assert events[0].interrupted_at == _NOW


@pytest.mark.unit
@pytest.mark.parametrize(
    "terminal",
    [RunStatus.COMPLETED, RunStatus.ABORTED, RunStatus.STOPPED, RunStatus.TRUNCATED],
)
def test_decide_raises_cannot_truncate_from_any_terminal(terminal: RunStatus) -> None:
    state = _run(status=terminal)
    with pytest.raises(RunCannotTruncateError) as exc_info:
        truncate_run.decide(
            state=state,
            command=TruncateRun(run_id=state.id, reason="X", interrupted_at=None),
            now=_NOW,
        )
    assert exc_info.value.current_status is terminal


@pytest.mark.unit
def test_decide_error_message_names_required_running_or_held_status() -> None:
    state = _run(status=RunStatus.COMPLETED)
    with pytest.raises(RunCannotTruncateError) as exc_info:
        truncate_run.decide(
            state=state,
            command=TruncateRun(run_id=state.id, reason="X", interrupted_at=None),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Running" in msg
    assert "Held" in msg


@pytest.mark.unit
def test_decide_validates_reason_before_status_guard() -> None:
    """Validation order: reason VO runs before the FSM guard.

    A whitespace-only reason from a terminal state should raise the
    reason error, not the cannot-truncate error. Same precedent as
    stop_run's decider — the reason is intrinsic to the command,
    state-relative checks come after.
    """
    state = _run(status=RunStatus.COMPLETED)
    with pytest.raises(InvalidRunTruncateReasonError):
        truncate_run.decide(
            state=state,
            command=TruncateRun(run_id=state.id, reason="   ", interrupted_at=None),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _run()
    command = TruncateRun(run_id=state.id, reason="X", interrupted_at=_INTERRUPTED_AT)
    first = truncate_run.decide(state=state, command=command, now=_NOW)
    second = truncate_run.decide(state=state, command=command, now=_NOW)
    assert first == second
