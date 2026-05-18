"""Read repository for the Supply aggregate.

`load_supply(event_store, supply_id) -> Supply | None` mirrors
`load_family` / `load_asset` / `load_subject`. Used by the
`get_supply` query slice (10a-a) and update-style command handlers
(10a-a `mark_supply_available`; 10a-b transition slices).
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.supply.aggregates.supply.events import from_stored
from cora.supply.aggregates.supply.evolver import fold
from cora.supply.aggregates.supply.state import Supply

_STREAM_TYPE = "Supply"


async def load_supply(event_store: EventStore, supply_id: UUID) -> Supply | None:
    """Load and fold a Supply's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, supply_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
