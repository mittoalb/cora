"""Evolver: replay events to reconstruct Surface state.

Mirror of `cora/trust/aggregates/zone/evolver.py`. Future
SurfaceVersioned / SurfaceDeprecated events extend the match;
exhaustiveness guard catches missed arms.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.trust.aggregates.surface.events import SurfaceDefined, SurfaceEvent
from cora.trust.aggregates.surface.state import Surface, SurfaceName, SurfaceStatus


def evolve(state: Surface | None, event: SurfaceEvent) -> Surface:
    """Apply one event to the current state."""
    match event:
        case SurfaceDefined(surface_id=surface_id, name=name, kind=kind, occurred_at=occurred_at):
            _ = state  # SurfaceDefined is genesis; prior state ignored
            return Surface(
                id=surface_id,
                name=SurfaceName(name),
                kind=kind,
                status=SurfaceStatus.DEFINED,
                defined_at=occurred_at,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[SurfaceEvent]) -> Surface | None:
    """Replay a stream of events from the empty initial state."""
    state: Surface | None = None
    for event in events:
        state = evolve(state, event)
    return state
