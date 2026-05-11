"""Evolver: replay events to reconstruct Conduit state.

Mirror of `cora/trust/aggregates/zone/evolver.py`. The terminal
`assert_never` case forces pyright (and the runtime) to error if a
new event type is added to `ConduitEvent` without a matching match
arm.

Phase 6f-5a adds two logbook-lifecycle event arms over the
`logbooks: dict[str, UUID]` state shape:
  - `ConduitLogbookOpened` adds `(kind, logbook_id)` to `logbooks`,
    enforcing the at-most-one-open-per-kind invariant — opening a
    second logbook of an existing kind raises
    `ConduitLogbookAlreadyOpenError` carrying the existing logbook id.
  - `ConduitLogbookClosed` finds the kind that owns the closed
    logbook id and removes that entry; raises
    `ConduitLogbookNotOpenError` if no kind owns the id.

Defensive guards: both arms raise on `state is None` (the parent
Conduit must exist before any logbook can attach to it). The
evolver returns a fresh `Conduit` with a new `logbooks` dict on
every logbook-open / logbook-close — the dict is never mutated in
place. Frozen dataclass blocks field reassignment but not dict
mutation; the codebase relies on the same evolver-purity discipline
used by every other aggregate.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.trust.aggregates.conduit.events import (
    ConduitDefined,
    ConduitEvent,
    ConduitLogbookClosed,
    ConduitLogbookOpened,
)
from cora.trust.aggregates.conduit.state import (
    Conduit,
    ConduitLogbookAlreadyOpenError,
    ConduitLogbookNotOpenError,
    ConduitName,
)


def evolve(state: Conduit | None, event: ConduitEvent) -> Conduit:
    """Apply one event to the current state."""
    match event:
        case ConduitDefined(
            conduit_id=conduit_id,
            name=name,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
        ):
            _ = state  # ConduitDefined is the genesis event; prior state ignored
            return Conduit(
                id=conduit_id,
                name=ConduitName(name),
                source_zone_id=source_zone_id,
                target_zone_id=target_zone_id,
            )
        case ConduitLogbookOpened(logbook_id=logbook_id, kind=kind):
            if state is None:
                msg = "ConduitLogbookOpened before ConduitDefined: stream is corrupted"
                raise ValueError(msg)
            existing = state.logbooks.get(kind)
            if existing is not None:
                raise ConduitLogbookAlreadyOpenError(state.id, kind, existing)
            return replace(state, logbooks={**state.logbooks, kind: logbook_id})
        case ConduitLogbookClosed(logbook_id=logbook_id):
            if state is None:
                msg = "ConduitLogbookClosed before ConduitDefined: stream is corrupted"
                raise ValueError(msg)
            matching_kind = next(
                (k for k, v in state.logbooks.items() if v == logbook_id),
                None,
            )
            if matching_kind is None:
                raise ConduitLogbookNotOpenError(state.id, logbook_id)
            return replace(
                state,
                logbooks={k: v for k, v in state.logbooks.items() if k != matching_kind},
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ConduitEvent]) -> Conduit | None:
    """Replay a stream of events from the empty initial state."""
    state: Conduit | None = None
    for event in events:
        state = evolve(state, event)
    return state
