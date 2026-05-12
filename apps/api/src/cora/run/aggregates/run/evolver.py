"""Evolver: replay events to reconstruct Run state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `RunEvent` without a matching match arm here.

Status mapping per event type:
  - `RunStarted`   -> RUNNING   (genesis; the start-event puts the
                                 Run into the active steady-state)
  - `RunHeld`      -> HELD      (pause)
  - `RunResumed`   -> RUNNING   (un-pause; back to the active steady-state)
  - `RunCompleted` -> COMPLETED (happy-path terminal)
  - `RunAborted`   -> ABORTED   (emergency-exit terminal)
  - `RunStopped`   -> STOPPED   (controlled-exit terminal)
  - `RunTruncated` -> TRUNCATED (partial-data terminal)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `PlanDefined → DEFINED` / `PlanVersioned → VERSIONED` /
`PlanDeprecated → DEPRECATED` / `SubjectMounted → MOUNTED`.

Transition events preserve `id`, `name`, `plan_id`, `subject_id`
from the prior state (they're absent from the slim transition
payloads — the event type alone updates `status`).

Hold ⇄ Resume is the first bidirectional cycle in any Run aggregate
event stream. The fold is order-sensitive (replay is sequential) so
[RunHeld, RunResumed, RunHeld, RunResumed, RunCompleted] correctly
yields COMPLETED. Per-cycle audit lives in the event stream itself;
the aggregate state only carries the latest status (slim-aggregate
principle, gate-review 6f-3 L9 lock).

Defensive guards: every transition event raises on `state is None`
because no fold path produces a transition event before a genesis.
The deciders enforce this at command time, but the evolver also
asserts it so a contaminated stream (foreign or out-of-order events)
fails loud rather than silently producing a defaulted aggregate.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.run.aggregates.run.events import (
    RunAborted,
    RunCompleted,
    RunEvent,
    RunHeld,
    RunResumed,
    RunStarted,
    RunStopped,
    RunTruncated,
)
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
        case RunHeld():
            if state is None:
                msg = "RunHeld before RunStarted: stream is corrupted"
                raise ValueError(msg)
            return replace(state, status=RunStatus.HELD)
        case RunResumed():
            if state is None:
                msg = "RunResumed before RunStarted: stream is corrupted"
                raise ValueError(msg)
            return replace(state, status=RunStatus.RUNNING)
        case RunCompleted():
            if state is None:
                msg = "RunCompleted before RunStarted: stream is corrupted"
                raise ValueError(msg)
            return replace(state, status=RunStatus.COMPLETED)
        case RunAborted():
            if state is None:
                msg = "RunAborted before RunStarted: stream is corrupted"
                raise ValueError(msg)
            return replace(state, status=RunStatus.ABORTED)
        case RunStopped():
            if state is None:
                msg = "RunStopped before RunStarted: stream is corrupted"
                raise ValueError(msg)
            return replace(state, status=RunStatus.STOPPED)
        case RunTruncated():
            if state is None:
                msg = "RunTruncated before RunStarted: stream is corrupted"
                raise ValueError(msg)
            return replace(state, status=RunStatus.TRUNCATED)
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[RunEvent]) -> Run | None:
    """Replay a stream of events from the empty initial state."""
    state: Run | None = None
    for event in events:
        state = evolve(state, event)
    return state
