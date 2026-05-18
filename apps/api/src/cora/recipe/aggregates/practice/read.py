"""Read repository for the Practice aggregate.

`load_practice(event_store, practice_id) -> Practice | None` mirrors
`load_method` / `load_family` / `load_actor` / etc. Used by the
`get_practice` query slice (6d-1) and any future update-style
commands (6d-2).
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.recipe.aggregates.practice.events import from_stored
from cora.recipe.aggregates.practice.evolver import fold
from cora.recipe.aggregates.practice.state import Practice

_STREAM_TYPE = "Practice"


async def load_practice(event_store: EventStore, practice_id: UUID) -> Practice | None:
    """Load and fold a Practice's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, practice_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
