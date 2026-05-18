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

**Critical invariant**: every transition arm MUST carry `id`,
`name`, `source_zone_id`, `target_zone_id` through from prior
state, and either preserve or rewrite `logbooks` deliberately.
Constructing `Conduit(id=..., name=..., source_zone_id=...,
target_zone_id=...)` without explicitly passing `logbooks` would
silently WIPE the dict to its empty default. Aligned to explicit
construction post-domain-audit to match the documented pattern in
Asset/Plan/Method/Practice/Family/Subject evolvers.

Defensive guards: both arms raise on `state is None` (the parent
Conduit must exist before any logbook can attach to it). The
evolver returns a fresh `Conduit` with a new `logbooks` dict on
every logbook-open / logbook-close — the dict is never mutated in
place. Frozen dataclass blocks field reassignment but not dict
mutation; the codebase relies on the same evolver-purity discipline
used by every other aggregate.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
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
            prior = require_state(state, "ConduitLogbookOpened")
            existing = prior.logbooks.get(kind)
            if existing is not None:
                raise ConduitLogbookAlreadyOpenError(prior.id, kind, existing)
            return Conduit(
                id=prior.id,
                name=prior.name,
                source_zone_id=prior.source_zone_id,
                target_zone_id=prior.target_zone_id,
                logbooks={**prior.logbooks, kind: logbook_id},
            )
        case ConduitLogbookClosed(logbook_id=logbook_id):
            prior = require_state(state, "ConduitLogbookClosed")
            matching_kind = next(
                (k for k, v in prior.logbooks.items() if v == logbook_id),
                None,
            )
            if matching_kind is None:
                raise ConduitLogbookNotOpenError(prior.id, logbook_id)
            return Conduit(
                id=prior.id,
                name=prior.name,
                source_zone_id=prior.source_zone_id,
                target_zone_id=prior.target_zone_id,
                logbooks={k: v for k, v in prior.logbooks.items() if k != matching_kind},
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ConduitEvent]) -> Conduit | None:
    """Replay a stream of events from the empty initial state."""
    state: Conduit | None = None
    for event in events:
        state = evolve(state, event)
    return state
