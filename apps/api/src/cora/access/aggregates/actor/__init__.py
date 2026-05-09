"""Actor aggregate: state, errors, events, evolver.

Vertical slices that operate on this aggregate live under
`cora.access.features.<verb>_actor/` and import from here for state and
event types.
"""

from cora.access.aggregates.actor.events import (
    ActorEvent,
    ActorRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.access.aggregates.actor.evolver import evolve, fold
from cora.access.aggregates.actor.state import (
    ACTOR_NAME_MAX_LENGTH,
    Actor,
    ActorAlreadyExistsError,
    ActorName,
    InvalidActorNameError,
)

__all__ = [
    "ACTOR_NAME_MAX_LENGTH",
    "Actor",
    "ActorAlreadyExistsError",
    "ActorEvent",
    "ActorName",
    "ActorRegistered",
    "InvalidActorNameError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "to_payload",
]
