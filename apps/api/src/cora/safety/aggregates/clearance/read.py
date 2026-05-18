"""Read repository for the Clearance aggregate.

`load_clearance(event_store, clearance_id) -> Clearance | None` mirrors
`load_supply` / `load_family` / `load_subject`. Used by the
`get_clearance` query slice (11a-a) and future update-style command
handlers (11a-b transitions; 11a-c expire / amend).
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.safety.aggregates.clearance.events import from_stored
from cora.safety.aggregates.clearance.evolver import fold
from cora.safety.aggregates.clearance.state import Clearance

_STREAM_TYPE = "Clearance"


async def load_clearance(event_store: EventStore, clearance_id: UUID) -> Clearance | None:
    """Load and fold a Clearance's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, clearance_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
