"""Evolver: replay events to reconstruct Practice state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `PracticeEvent` without a matching match arm here.

Status mapping per event type (6d-1 only ships the genesis event;
6d-2 adds the transitions):
  - `PracticeDefined` -> DEFINED  (genesis; current_version=None)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as MethodDefined / CapabilityDefined / SubjectMounted.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.recipe.aggregates.practice.events import (
    PracticeDefined,
    PracticeEvent,
)
from cora.recipe.aggregates.practice.state import (
    Practice,
    PracticeName,
    PracticeStatus,
)


def evolve(state: Practice | None, event: PracticeEvent) -> Practice:
    """Apply one event to the current state."""
    match event:
        case PracticeDefined(
            practice_id=practice_id,
            name=name,
            method_id=method_id,
            site_id=site_id,
        ):
            _ = state  # PracticeDefined is the genesis event; prior state ignored
            return Practice(
                id=practice_id,
                name=PracticeName(name),
                method_id=method_id,
                site_id=site_id,
                status=PracticeStatus.DEFINED,
                # current_version defaults to None.
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[PracticeEvent]) -> Practice | None:
    """Replay a stream of events from the empty initial state."""
    state: Practice | None = None
    for event in events:
        state = evolve(state, event)
    return state
