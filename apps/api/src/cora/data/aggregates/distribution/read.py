"""Read repository for the Distribution aggregate.

``load_distribution(event_store, distribution_id) -> Distribution | None``
mirrors ``load_dataset`` and the other single-aggregate fold-on-read
helpers. List / filter / search across Distributions goes through the
``proj_data_distribution_summary`` projection, not this read repo.
"""

from uuid import UUID

from cora.data.aggregates.distribution.events import from_stored
from cora.data.aggregates.distribution.evolver import fold
from cora.data.aggregates.distribution.state import Distribution
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Distribution"


async def load_distribution(event_store: EventStore, distribution_id: UUID) -> Distribution | None:
    """Load and fold a Distribution's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, distribution_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
