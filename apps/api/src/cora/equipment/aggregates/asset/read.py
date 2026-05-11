"""Read repository for the Asset aggregate.

`load_asset(event_store, asset_id) -> Asset | None` mirrors
`load_capability` / `load_subject` / `load_actor`. Used by the
`get_asset` query slice (5e) and any future update-style commands
(5c lifecycle, 5d hierarchy).
"""

from uuid import UUID

from cora.equipment.aggregates.asset.events import from_stored
from cora.equipment.aggregates.asset.evolver import fold
from cora.equipment.aggregates.asset.state import Asset
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Asset"


async def load_asset(event_store: EventStore, asset_id: UUID) -> Asset | None:
    """Load and fold an Asset's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, asset_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
