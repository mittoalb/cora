"""Read repository for the Conduit aggregate.

`load_conduit(event_store, conduit_id) -> Conduit | None` mirrors
`load_zone`. No GET slice for Conduit ships today; the read repo
lives here so future query slices, sagas, or projections have one
canonical fold-on-read path per the cross-BC pattern documented in
CONTRIBUTING.md.
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.trust.aggregates.conduit.events import from_stored
from cora.trust.aggregates.conduit.evolver import fold
from cora.trust.aggregates.conduit.state import Conduit

_STREAM_TYPE = "Conduit"


async def load_conduit(event_store: EventStore, conduit_id: UUID) -> Conduit | None:
    """Load and fold a Conduit's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, conduit_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
