"""Pure decider for the `AbortRun` command.

Single-source emergency-exit terminal: `Running -> Aborted`.
Aborting an already-terminal Run (Completed | Aborted) raises;
re-aborting an `Aborted` Run raises (strict-not-idempotent).

Source-state guard uses tuple-membership for forward-compat with
6f-3+ adding `Held` as an additional source if hold-then-abort
proves to be a real workflow (today: just `Running`).

`reason` validation goes through the `RunAbortReason` VO (which
calls the shared `validate_name` helper). The on-the-wire payload
in `RunAborted.reason` carries the trimmed string.

Invariants:
  - State must not be None  -> RunNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidRunAbortReasonError
  - State.status must be in {Running}
    -> RunCannotAbortError(current_status=...)
"""

from datetime import datetime

from cora.run.aggregates.run import (
    Run,
    RunAborted,
    RunAbortReason,
    RunCannotAbortError,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features.abort_run.command import AbortRun

_ABORTABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING,)


def decide(
    state: Run | None,
    command: AbortRun,
    *,
    now: datetime,
) -> list[RunAborted]:
    """Decide the events produced by aborting an existing Run."""
    if state is None:
        raise RunNotFoundError(command.run_id)
    reason = RunAbortReason(command.reason)
    if state.status not in _ABORTABLE_STATUSES:
        raise RunCannotAbortError(state.id, current_status=state.status)
    return [
        RunAborted(
            run_id=state.id,
            reason=reason.value,
            occurred_at=now,
        )
    ]
