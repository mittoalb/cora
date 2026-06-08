"""Read repository for the Facility aggregate.

`load_facility(event_store, facility_id) -> Facility | None` mirrors
`load_credential` / `load_permit` / `load_seal`. Used by the federation
BC's `decommission_facility` handler (which pre-loads the target
Facility before the decider) and by the future `get_facility` query
slice (deferred until consumer surfaces).

`load_facility_timestamps` is deferred to Sub-Slice B alongside the
`proj_federation_facility_summary` projection writer; the
`FacilityLifecycleTimestamps` VO at `state.py` is empty in Sub-Slice A
but kept so the read-tier import surface stays stable.
"""

from uuid import UUID

from cora.federation.aggregates.facility.events import from_stored
from cora.federation.aggregates.facility.evolver import fold
from cora.federation.aggregates.facility.state import Facility
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Facility"


async def load_facility(event_store: EventStore, facility_id: UUID) -> Facility | None:
    """Load and fold a Facility's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, facility_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
