"""Access domain layer: pure functional core.

The decider, evolver, value objects, and domain events for the Actor
aggregate. No I/O, no awaitables, no infrastructure imports — every
function in this package is referentially transparent.

Public surface:
    - Actor, ActorName             (state + value objects)
    - RegisterActor                (commands)
    - ActorRegistered, ActorEvent  (events)
    - register_actor               (decider)
    - evolve, fold                 (evolver + replay helper)
    - InvalidActorNameError,
      ActorAlreadyExistsError           (domain errors)
"""

from cora.access.domain.actor import (
    Actor,
    ActorAlreadyExistsError,
    ActorName,
    InvalidActorNameError,
)
from cora.access.domain.commands import RegisterActor
from cora.access.domain.events import ActorEvent, ActorRegistered
from cora.access.domain.evolver import evolve, fold
from cora.access.domain.register_actor import register_actor

__all__ = [
    "Actor",
    "ActorAlreadyExistsError",
    "ActorEvent",
    "ActorName",
    "ActorRegistered",
    "InvalidActorNameError",
    "RegisterActor",
    "evolve",
    "fold",
    "register_actor",
]
