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

Hold ⇄ Resume is the first bidirectional cycle in any Run aggregate
event stream. The fold is order-sensitive (replay is sequential) so
[RunHeld, RunResumed, RunHeld, RunResumed, RunCompleted] correctly
yields COMPLETED. Per-cycle audit lives in the event stream itself;
the aggregate state only carries the latest status (slim-aggregate
principle, gate-review 6f-3 L9 lock).

**Critical invariant**: every transition arm MUST carry `id`,
`name`, `plan_id`, `subject_id`, `raid`, `override_parameters`,
`effective_parameters`, AND `triggered_by` through from prior
state. Constructing `Run(id=..., name=..., plan_id=...,
subject_id=..., status=...)` without explicitly passing the
additive fields would silently WIPE them to defaults (empty dict
/ None). Pinned by the per-transition preserve-fields tests.

This evolver previously used `dataclasses.replace(state,
status=...)` for the transition arms (terse, but no field-add
review surface — new fields would silently carry through without
prompting evolver-arm review). Aligned to explicit construction
post-domain-audit to match the documented pattern in
Asset/Plan/Method/Practice/Capability/Subject evolvers.

Transition events applied to empty state raise ValueError: they
can never appear before `RunStarted` in a well-formed stream. The
`_require_state` helper keeps per-arm bodies short (precedent
locked by Subject's evolver in 4c).
"""

from collections.abc import Sequence
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


def _require_state(state: Run | None, event_type: str) -> Run:
    """Transition events require prior state; empty stream is corruption."""
    if state is None:
        msg = f"{event_type} cannot be applied to empty state"
        raise ValueError(msg)
    return state


def evolve(state: Run | None, event: RunEvent) -> Run:
    """Apply one event to the current state."""
    match event:
        case RunStarted(
            run_id=run_id,
            name=name,
            plan_id=plan_id,
            subject_id=subject_id,
            raid=raid,
            override_parameters=override_parameters,
            effective_parameters=effective_parameters,
            triggered_by=triggered_by,
        ):
            _ = state  # RunStarted is the genesis event; prior state ignored.
            return Run(
                id=run_id,
                name=RunName(name),
                plan_id=plan_id,
                subject_id=subject_id,
                raid=raid,
                status=RunStatus.RUNNING,
                override_parameters=override_parameters,
                effective_parameters=effective_parameters,
                triggered_by=triggered_by,
            )
        case RunHeld():
            prior = _require_state(state, "RunHeld")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.HELD,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
            )
        case RunResumed():
            prior = _require_state(state, "RunResumed")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.RUNNING,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
            )
        case RunCompleted():
            prior = _require_state(state, "RunCompleted")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.COMPLETED,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
            )
        case RunAborted():
            prior = _require_state(state, "RunAborted")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.ABORTED,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
            )
        case RunStopped():
            prior = _require_state(state, "RunStopped")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.STOPPED,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
            )
        case RunTruncated():
            prior = _require_state(state, "RunTruncated")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.TRUNCATED,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[RunEvent]) -> Run | None:
    """Replay a stream of events from the empty initial state."""
    state: Run | None = None
    for event in events:
        state = evolve(state, event)
    return state
