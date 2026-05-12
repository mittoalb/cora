"""Read repository for the Dataset aggregate.

`load_dataset(event_store, dataset_id) -> Dataset | None` mirrors
`load_actor` / `load_subject` / `load_run` / `load_zone` / etc.
Single-aggregate fold-on-read; list / filter / search across
Datasets requires a projection (deferred).
"""

from uuid import UUID

from cora.data.aggregates.dataset.events import from_stored
from cora.data.aggregates.dataset.evolver import fold
from cora.data.aggregates.dataset.state import Dataset
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Dataset"


async def load_dataset(event_store: EventStore, dataset_id: UUID) -> Dataset | None:
    """Load and fold a Dataset's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, dataset_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
