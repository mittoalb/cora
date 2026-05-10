"""Evolver: replay events to reconstruct Subject state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `SubjectEvent` without a matching match arm here.

Status mapping per event type:
  - `SubjectRegistered` -> RECEIVED  (genesis)
  - `SubjectMounted`    -> MOUNTED
  - `SubjectMeasured`   -> MEASURED
  - `SubjectRemoved`    -> REMOVED   (multi-source: Mounted | Measured)
  - `SubjectReturned`   -> RETURNED  (terminal disposition)
  - `SubjectStored`     -> STORED    (terminal disposition)
  - `SubjectDiscarded`  -> DISCARDED (terminal disposition)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `ActorDeactivated -> is_active=False`.

Transition events applied to empty state raise ValueError: they can
never appear before `SubjectRegistered` in a well-formed stream.
The shared guard helper keeps the per-arm bodies short.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.subject.aggregates.subject.events import (
    SubjectDiscarded,
    SubjectEvent,
    SubjectMeasured,
    SubjectMounted,
    SubjectRegistered,
    SubjectRemoved,
    SubjectReturned,
    SubjectStored,
)
from cora.subject.aggregates.subject.state import Subject, SubjectName, SubjectStatus


def _require_state(state: Subject | None, event_type: str) -> Subject:
    """Transition events require prior state; empty stream is corruption."""
    if state is None:
        msg = f"{event_type} cannot be applied to empty state"
        raise ValueError(msg)
    return state


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
            prior = _require_state(state, "SubjectMounted")
            return Subject(id=prior.id, name=prior.name, status=SubjectStatus.MOUNTED)
        case SubjectMeasured():
            prior = _require_state(state, "SubjectMeasured")
            return Subject(id=prior.id, name=prior.name, status=SubjectStatus.MEASURED)
        case SubjectRemoved():
            prior = _require_state(state, "SubjectRemoved")
            return Subject(id=prior.id, name=prior.name, status=SubjectStatus.REMOVED)
        case SubjectReturned():
            prior = _require_state(state, "SubjectReturned")
            return Subject(id=prior.id, name=prior.name, status=SubjectStatus.RETURNED)
        case SubjectStored():
            prior = _require_state(state, "SubjectStored")
            return Subject(id=prior.id, name=prior.name, status=SubjectStatus.STORED)
        case SubjectDiscarded():
            prior = _require_state(state, "SubjectDiscarded")
            return Subject(id=prior.id, name=prior.name, status=SubjectStatus.DISCARDED)
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[SubjectEvent]) -> Subject | None:
    """Replay a stream of events from the empty initial state."""
    state: Subject | None = None
    for event in events:
        state = evolve(state, event)
    return state
