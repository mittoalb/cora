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

from collections.abc import Sequence
from typing import assert_never

from cora.access.aggregates.actor.events import (
    ActorDeactivated,
    ActorEvent,
    ActorRegistered,
)
from cora.access.aggregates.actor.state import Actor, ActorName


def evolve(state: Actor | None, event: ActorEvent) -> Actor:
    """Apply one event to the current state."""
    match event:
        case ActorRegistered(actor_id=actor_id, name=name, kind=kind):
            # `is_active=True` is explicit-vs-default; mutmut flags omitting
            # it as a surviving mutant (equivalent), so silence that line.
            return Actor(
                id=actor_id,
                name=ActorName(name),
                is_active=True,  # pragma: no mutate
                kind=kind,
            )
        case ActorDeactivated():
            if state is None:  # pragma: no cover  # corruption guard
                # ActorDeactivated never appears before ActorRegistered in a
                # well-formed stream; if it does, the stream is corrupted.
                # Block is unreachable in well-formed streams (already `no
                # cover`); silence mutmut on the message/raise too.
                msg = "ActorDeactivated cannot be applied to empty state"  # pragma: no mutate
                raise ValueError(msg)  # pragma: no mutate
            return Actor(id=state.id, name=state.name, is_active=False, kind=state.kind)
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)  # pragma: no mutate


def fold(events: Sequence[ActorEvent]) -> Actor | None:
    """Replay a stream of events from the empty initial state.

    `Sequence` (covariant) rather than `list` (invariant) so callers can
    pass `list[ActorRegistered]` (a single-variant subtype) without an
    explicit cast -- matters in tests that build small homogeneous lists.
    """
    state: Actor | None = None
    for event in events:
        state = evolve(state, event)
    return state
