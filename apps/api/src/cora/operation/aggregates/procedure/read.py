"""Read repository for the Procedure aggregate.

`load_procedure(event_store, procedure_id) -> Procedure | None`
mirrors `load_supply` / `load_capability` / `load_subject`. Used by
the `get_procedure` query slice (10c-a) and update-style command
handlers (10c-b transition slices).
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.operation.aggregates.procedure.events import from_stored
from cora.operation.aggregates.procedure.evolver import fold
from cora.operation.aggregates.procedure.state import Procedure

_STREAM_TYPE = "Procedure"


async def load_procedure(event_store: EventStore, procedure_id: UUID) -> Procedure | None:
    """Load and fold a Procedure's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, procedure_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
