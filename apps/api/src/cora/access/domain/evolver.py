"""Evolver: replay events to reconstruct Actor state.

`evolve(state, event) -> state` applies a single event to the current
state. `fold(events) -> state | None` is the convenience that walks an
event list from the empty initial state, used by the application handler
after loading a stream from the EventStore.

Both functions are pure and total: every (state, event) pair has a
single deterministic result. New event types are added by extending the
match statement.
"""

from cora.access.domain.actor import Actor, ActorName
from cora.access.domain.events import ActorEvent, ActorRegistered


def evolve(state: Actor | None, event: ActorEvent) -> Actor:
    """Apply one event to the current state."""
    match event:
        case ActorRegistered(actor_id=actor_id, name=name):
            return Actor(id=actor_id, name=ActorName(name))


def fold(events: list[ActorEvent]) -> Actor | None:
    """Replay a stream of events from the empty initial state."""
    state: Actor | None = None
    for event in events:
        state = evolve(state, event)
    return state
