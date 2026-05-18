"""Read repository for the Run aggregate.

`load_run(event_store, run_id) -> Run | None` mirrors `load_plan` /
`load_practice` / `load_method` / `load_family` / `load_actor` /
`load_subject` / `load_asset`. Used by the `get_run` query slice
(6f-1) and any future update-style commands (6f-2+).
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.run.aggregates.run.events import from_stored
from cora.run.aggregates.run.evolver import fold
from cora.run.aggregates.run.state import Run

_STREAM_TYPE = "Run"


async def load_run(event_store: EventStore, run_id: UUID) -> Run | None:
    """Load and fold a Run's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, run_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
