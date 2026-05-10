"""Evolver: replay events to reconstruct Subject state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `SubjectEvent` without a matching match arm here.

`SubjectRegistered` sets status to `Received` (the genesis state).
Future transition events (4b+) flip the status field per the locked
enum-in-state, str-in-event convention documented on the aggregate.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.subject.aggregates.subject.events import SubjectEvent, SubjectRegistered
from cora.subject.aggregates.subject.state import Subject, SubjectName, SubjectStatus


def evolve(state: Subject | None, event: SubjectEvent) -> Subject:
    """Apply one event to the current state."""
    match event:
        case SubjectRegistered(subject_id=subject_id, name=name):
            _ = state  # SubjectRegistered is the genesis event; prior state ignored
            return Subject(
                id=subject_id,
                name=SubjectName(name),
                status=SubjectStatus.RECEIVED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[SubjectEvent]) -> Subject | None:
    """Replay a stream of events from the empty initial state."""
    state: Subject | None = None
    for event in events:
        state = evolve(state, event)
    return state
