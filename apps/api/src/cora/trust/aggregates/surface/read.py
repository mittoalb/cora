"""Read repository for the Surface aggregate."""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.trust.aggregates.surface.events import from_stored
from cora.trust.aggregates.surface.evolver import fold
from cora.trust.aggregates.surface.state import Surface

_STREAM_TYPE = "Surface"


async def load_surface(event_store: EventStore, surface_id: UUID) -> Surface | None:
    """Load and fold a Surface's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, surface_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
