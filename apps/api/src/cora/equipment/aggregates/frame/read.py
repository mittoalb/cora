"""Read repository for the Frame aggregate.

`load_frame(event_store, frame_id) -> Frame | None` mirrors
`load_asset`. Used by update-style commands (`update_frame`,
`decommission_frame`) that need to load + fold before deciding.
"""

from uuid import UUID

from cora.equipment.aggregates.frame.events import from_stored
from cora.equipment.aggregates.frame.evolver import fold
from cora.equipment.aggregates.frame.state import Frame
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Frame"


async def load_frame(event_store: EventStore, frame_id: UUID) -> Frame | None:
    """Load and fold a Frame's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, frame_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
