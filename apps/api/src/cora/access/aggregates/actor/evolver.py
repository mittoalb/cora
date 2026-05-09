"""Evolver: replay events to reconstruct Actor state.

`evolve(state, event) -> state` applies a single event to the current
state. `fold(events) -> state | None` is the convenience that walks an
event list from the empty initial state, used by the application handler
after loading a stream from the EventStore.

Both functions are pure and total: every (state, event) pair has a
single deterministic result. The terminal `assert_never` case forces
pyright (and the runtime) to error if a new event type is added to
`ActorEvent` without a matching match arm here, so the evolver can
never silently return None for an unhandled event.
"""

from typing import assert_never

from cora.access.aggregates.actor.events import ActorEvent, ActorRegistered
from cora.access.aggregates.actor.state import Actor, ActorName


def evolve(state: Actor | None, event: ActorEvent) -> Actor:
    """Apply one event to the current state."""
    match event:
        case ActorRegistered(actor_id=actor_id, name=name):
            return Actor(id=actor_id, name=ActorName(name))
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: list[ActorEvent]) -> Actor | None:
    """Replay a stream of events from the empty initial state."""
    state: Actor | None = None
    for event in events:
        state = evolve(state, event)
    return state
