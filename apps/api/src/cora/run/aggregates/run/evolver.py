"""Evolver: replay events to reconstruct Run state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `RunEvent` without a matching match arm here. (Single
event type today; 6f-2+ adds transition events.)

Status mapping per event type:
  - `RunStarted` -> RUNNING  (genesis; the start-event puts the Run
                              into the active steady-state)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `PlanDefined → DEFINED` / `PracticeDefined → DEFINED`
/ `MethodDefined → DEFINED` / `CapabilityDefined → DEFINED` /
`SubjectMounted → MOUNTED` / `ActorDeactivated → is_active=False`.

`subject_id` is preserved as None or UUID through the fold (no
intermediate transformation); same shape as the event payload.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.run.aggregates.run.events import RunEvent, RunStarted
from cora.run.aggregates.run.state import Run, RunName, RunStatus


def evolve(state: Run | None, event: RunEvent) -> Run:
    """Apply one event to the current state."""
    match event:
        case RunStarted(
            run_id=run_id,
            name=name,
            plan_id=plan_id,
            subject_id=subject_id,
        ):
            _ = state  # RunStarted is the genesis event; prior state ignored.
            return Run(
                id=run_id,
                name=RunName(name),
                plan_id=plan_id,
                subject_id=subject_id,
                status=RunStatus.RUNNING,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[RunEvent]) -> Run | None:
    """Replay a stream of events from the empty initial state."""
    state: Run | None = None
    for event in events:
        state = evolve(state, event)
    return state
