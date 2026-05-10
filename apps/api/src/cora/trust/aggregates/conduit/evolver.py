"""Evolver: replay events to reconstruct Conduit state.

Mirror of `cora/trust/aggregates/zone/evolver.py`. The terminal
`assert_never` case forces pyright (and the runtime) to error if a
new event type is added to `ConduitEvent` without a matching match
arm.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.trust.aggregates.conduit.events import ConduitDefined, ConduitEvent
from cora.trust.aggregates.conduit.state import Conduit, ConduitName


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
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ConduitEvent]) -> Conduit | None:
    """Replay a stream of events from the empty initial state."""
    state: Conduit | None = None
    for event in events:
        state = evolve(state, event)
    return state
