"""Domain events for the Access BC.

Events are facts that happened. They are plain frozen dataclasses,
named with PascalCase past-tense verbs (`ActorRegistered`). The
application handler converts each domain event to an
`infrastructure.ports.event_store.NewEvent` for persistence; until then
events are pure values, suitable for use in the decider's return type
and the evolver's input.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ActorRegistered:
    """A new actor was registered."""

    actor_id: UUID
    name: str
    occurred_at: datetime


# Discriminated union of every event the Access BC emits. Grows as
# new commands and events are added (e.g. ActorRenamed, ActorDeactivated).
ActorEvent = ActorRegistered
