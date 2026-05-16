"""Read repository for the Caution aggregate.

`load_caution(event_store, caution_id) -> Caution | None` mirrors
`load_supply` / `load_clearance` / `load_asset`. Used by the
`get_caution` query slice and the update-style handlers
(`supersede_caution` pre-loads the parent; `retire_caution` loads the
target Caution before the decider).
"""

from uuid import UUID

from cora.caution.aggregates.caution.events import from_stored
from cora.caution.aggregates.caution.evolver import fold
from cora.caution.aggregates.caution.state import Caution
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Caution"


async def load_caution(event_store: EventStore, caution_id: UUID) -> Caution | None:
    """Load and fold a Caution's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, caution_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
