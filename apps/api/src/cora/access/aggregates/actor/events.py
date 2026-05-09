"""Domain events emitted by the Actor aggregate, plus the discriminated union.

Events live in the aggregate folder (not the slice) because they are
intrinsic facts about the aggregate's history — the slice just decides
when to emit them. The evolver dispatches on the union; new event types
are appended both as a class definition and to the union alias.
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


# When ActorDeactivated, ActorRenamed, etc. land they're added here:
#   ActorEvent = ActorRegistered | ActorDeactivated
ActorEvent = ActorRegistered

__all__ = ["ActorEvent", "ActorRegistered"]
