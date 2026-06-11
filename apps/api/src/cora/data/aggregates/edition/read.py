"""Read repository for the Edition aggregate.

`load_edition(event_store, edition_id) -> Edition | None` mirrors
`load_distribution` / `load_dataset` and the other single-aggregate
fold-on-read helpers. List / filter / search across Editions goes
through the `proj_data_edition_summary` projection, not this read
repo.
"""

from uuid import UUID

from cora.data.aggregates.edition.events import from_stored
from cora.data.aggregates.edition.evolver import fold
from cora.data.aggregates.edition.state import Edition
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Edition"


async def load_edition(event_store: EventStore, edition_id: UUID) -> Edition | None:
    """Load and fold an Edition's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, edition_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


__all__ = ["load_edition"]
