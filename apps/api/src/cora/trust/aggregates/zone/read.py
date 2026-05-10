"""Read repository for the Zone aggregate.

`load_zone(event_store, zone_id) -> Zone | None` mirrors
`cora.access.aggregates.actor.read.load_actor`. No GET slice for Zone
ships in Phase 3a, but the read repo lives here so future query
slices (or sagas / projections) have one canonical fold-on-read path
per the cross-BC pattern documented in CONTRIBUTING.md.
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.trust.aggregates.zone.events import from_stored
from cora.trust.aggregates.zone.evolver import fold
from cora.trust.aggregates.zone.state import Zone

_STREAM_TYPE = "Zone"


async def load_zone(event_store: EventStore, zone_id: UUID) -> Zone | None:
    """Load and fold a Zone's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, zone_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
