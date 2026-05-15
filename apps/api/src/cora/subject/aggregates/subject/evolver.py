"""Evolver: replay events to reconstruct Subject state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `SubjectEvent` without a matching match arm here.

Status mapping per event type:
  - `SubjectRegistered` -> RECEIVED  (genesis)
  - `SubjectMounted`    -> MOUNTED
  - `SubjectMeasured`   -> MEASURED
  - `SubjectDismounted` -> RECEIVED  (4f: Mounted | Measured -> Received cycle)
  - `SubjectRemoved`    -> REMOVED   (multi-source: Mounted | Measured | Received)
  - `SubjectReturned`   -> RETURNED  (terminal disposition)
  - `SubjectStored`     -> STORED    (terminal disposition)
  - `SubjectDiscarded`  -> DISCARDED (terminal disposition)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `ActorDeactivated -> is_active=False`.

`mounted_on_asset_id`: set on SubjectMounted (from event.asset_id),
preserved through SubjectMeasured (from prior state), cleared on
SubjectRemoved and the terminal dispositions. None on the Received
genesis state.

Transition events applied to empty state raise ValueError: they can
never appear before `SubjectRegistered` in a well-formed stream.
The shared guard helper keeps the per-arm bodies short.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.subject.aggregates.subject.events import (
    SubjectDiscarded,
    SubjectDismounted,
    SubjectEvent,
    SubjectMeasured,
    SubjectMounted,
    SubjectRegistered,
    SubjectRemoved,
    SubjectReturned,
    SubjectStored,
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
                mounted_on_asset_id=None,
            )
        case SubjectMounted(asset_id=asset_id):
            prior = require_state(state, "SubjectMounted")
            return Subject(
                id=prior.id,
                name=prior.name,
                status=SubjectStatus.MOUNTED,
                mounted_on_asset_id=asset_id,
            )
        case SubjectMeasured():
            prior = require_state(state, "SubjectMeasured")
            return Subject(
                id=prior.id,
                name=prior.name,
                status=SubjectStatus.MEASURED,
                mounted_on_asset_id=prior.mounted_on_asset_id,
            )
        case SubjectRemoved():
            prior = require_state(state, "SubjectRemoved")
            return Subject(
                id=prior.id,
                name=prior.name,
                status=SubjectStatus.REMOVED,
                mounted_on_asset_id=None,
            )
        case SubjectReturned():
            prior = require_state(state, "SubjectReturned")
            return Subject(
                id=prior.id,
                name=prior.name,
                status=SubjectStatus.RETURNED,
                mounted_on_asset_id=None,
            )
        case SubjectStored():
            prior = require_state(state, "SubjectStored")
            return Subject(
                id=prior.id,
                name=prior.name,
                status=SubjectStatus.STORED,
                mounted_on_asset_id=None,
            )
        case SubjectDiscarded():
            prior = require_state(state, "SubjectDiscarded")
            return Subject(
                id=prior.id,
                name=prior.name,
                status=SubjectStatus.DISCARDED,
                mounted_on_asset_id=None,
            )
        case SubjectDismounted():
            # 4f: physical-mount cycle. Status returns to Received
            # (sample is in the lab, not currently mounted) so the
            # mount_subject decider's source-state guard naturally
            # supports re-mount. mounted_on_asset_id cleared. The
            # event payload's from_asset_id and reason are audit
            # metadata, not folded into state.
            prior = require_state(state, "SubjectDismounted")
            return Subject(
                id=prior.id,
                name=prior.name,
                status=SubjectStatus.RECEIVED,
                mounted_on_asset_id=None,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[SubjectEvent]) -> Subject | None:
    """Replay a stream of events from the empty initial state."""
    state: Subject | None = None
    for event in events:
        state = evolve(state, event)
    return state
