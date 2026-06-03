"""Read repository for the Fixture aggregate."""

from uuid import UUID

from cora.equipment.aggregates.fixture.events import from_stored
from cora.equipment.aggregates.fixture.evolver import fold
from cora.equipment.aggregates.fixture.state import Fixture
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Fixture"


async def load_fixture(
    event_store: EventStore,
    fixture_id: UUID,
) -> Fixture | None:
    """Load and fold a Fixture's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, fixture_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
