"""Read repository for the Family aggregate.

`load_family(event_store, family_id) -> Family | None` mirrors
`load_actor` / `load_subject` / `load_zone` / etc.

## Stream type after rename

`_STREAM_TYPE = "Family"`. The stream-type string is the event store's
internal categorization key. CORA is greenfield (no production
deployments at 5i lock time), so changing the stream key to match the
new aggregate name is the simpler choice; if a future deployment ever
needs to read pre-5i streams written under the old `"Capability"`
stream type, add a one-time migration that updates `events.stream_type`
to `"Family"` (the event payloads themselves stay untouched per
[[project-immutability-guarantee]]; only the categorization label
changes). Watch item documented in DLM-A.
"""

from uuid import UUID

from cora.equipment.aggregates.family.events import from_stored
from cora.equipment.aggregates.family.evolver import fold
from cora.equipment.aggregates.family.state import Family
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Family"


async def load_family(event_store: EventStore, family_id: UUID) -> Family | None:
    """Load and fold a Family's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, family_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
