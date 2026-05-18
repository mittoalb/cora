"""Read repository for the Method aggregate.

`load_method(event_store, method_id) -> Method | None` mirrors
`load_family` / `load_actor` / `load_subject` / `load_zone` /
`load_conduit` / `load_policy` / `load_asset`. Used by the
`get_method` query slice (6a) and any future update-style commands
(6b).
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.recipe.aggregates.method.events import from_stored
from cora.recipe.aggregates.method.evolver import fold
from cora.recipe.aggregates.method.state import Method

_STREAM_TYPE = "Method"


async def load_method(event_store: EventStore, method_id: UUID) -> Method | None:
    """Load and fold a Method's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, method_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
