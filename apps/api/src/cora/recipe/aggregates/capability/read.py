"""Read repository for the Capability aggregate.

`load_capability(event_store, capability_id) -> Capability | None`
mirrors `load_family` / `load_method` / `load_plan` / etc.
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.recipe.aggregates.capability.events import from_stored
from cora.recipe.aggregates.capability.evolver import fold
from cora.recipe.aggregates.capability.state import Capability

_STREAM_TYPE = "Capability"


async def load_capability(event_store: EventStore, capability_id: UUID) -> Capability | None:
    """Load and fold a Capability's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, capability_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
