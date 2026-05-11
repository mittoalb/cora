"""Read repository for the Capability aggregate.

`load_capability(event_store, capability_id) -> Capability | None`
mirrors `load_actor` / `load_subject` / `load_zone` /
`load_conduit` / `load_policy`. Used by the `get_capability` query
slice (5a) and any future update-style commands (5f+).
"""

from uuid import UUID

from cora.equipment.aggregates.capability.events import from_stored
from cora.equipment.aggregates.capability.evolver import fold
from cora.equipment.aggregates.capability.state import Capability
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Capability"


async def load_capability(event_store: EventStore, capability_id: UUID) -> Capability | None:
    """Load and fold a Capability's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, capability_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
