"""Read repository for the Subject aggregate.

`load_subject(event_store, subject_id) -> Subject | None` mirrors
`load_actor` / `load_zone` / `load_conduit` / `load_policy`. No GET
slice ships with the genesis command; the read repo lives here so
update-style commands (mount, measure, remove) and the get_subject
query slice have one canonical fold-on-read path per the cross-BC
pattern.
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.subject.aggregates.subject.events import from_stored
from cora.subject.aggregates.subject.evolver import fold
from cora.subject.aggregates.subject.state import Subject

_STREAM_TYPE = "Subject"


async def load_subject(event_store: EventStore, subject_id: UUID) -> Subject | None:
    """Load and fold a Subject's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, subject_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
