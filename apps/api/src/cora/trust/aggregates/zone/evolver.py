"""Evolver: replay events to reconstruct Zone state.

`evolve(state, event) -> state` applies a single event to the current
state. `fold(events) -> state | None` walks an event list from the
empty initial state. Both are pure and total. Mirror of
`cora/access/aggregates/actor/evolver.py`.

The terminal `assert_never` case forces pyright (and the runtime) to
error if a new event type is added to `ZoneEvent` without a matching
match arm, so the evolver can never silently ignore an unhandled
event.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.trust.aggregates.zone.events import ZoneDefined, ZoneEvent
from cora.trust.aggregates.zone.state import Zone, ZoneName


def evolve(state: Zone | None, event: ZoneEvent) -> Zone:
    """Apply one event to the current state."""
    match event:
        case ZoneDefined(zone_id=zone_id, name=name):
            _ = state  # ZoneDefined is the genesis event; prior state ignored
            return Zone(id=zone_id, name=ZoneName(name))
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ZoneEvent]) -> Zone | None:
    """Replay a stream of events from the empty initial state."""
    state: Zone | None = None
    for event in events:
        state = evolve(state, event)
    return state
