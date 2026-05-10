"""Evolver: replay events to reconstruct Subject state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `SubjectEvent` without a matching match arm here.

`SubjectRegistered` sets status to `Received` (the genesis state).
`SubjectMounted` sets status to `Mounted`. The status mapping is
hardcoded per match arm — the event type IS the state-change
indicator (no status field in event payloads). Same precedent as
`ActorDeactivated -> is_active=False`.

`SubjectMounted` applied to empty state raises ValueError: it can
never appear before `SubjectRegistered` in a well-formed stream.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.subject.aggregates.subject.events import (
    SubjectEvent,
    SubjectMounted,
    SubjectRegistered,
)
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
        case SubjectMounted():
            if state is None:
                # SubjectMounted never appears before SubjectRegistered in a
                # well-formed stream; if it does, the stream is corrupted.
                msg = "SubjectMounted cannot be applied to empty state"
                raise ValueError(msg)
            return Subject(
                id=state.id,
                name=state.name,
                status=SubjectStatus.MOUNTED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[SubjectEvent]) -> Subject | None:
    """Replay a stream of events from the empty initial state."""
    state: Subject | None = None
    for event in events:
        state = evolve(state, event)
    return state
