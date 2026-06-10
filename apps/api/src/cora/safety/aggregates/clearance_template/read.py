"""Read repository for the ClearanceTemplate aggregate.

`load_clearance_template(event_store, template_id) -> ClearanceTemplate | None`
mirrors `load_family` / `load_actor` / `load_subject` / etc.

Same pattern: fetch the event stream from the event store, upcast events
via `from_stored`, and fold them via the evolver to reconstruct current state.
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.safety.aggregates.clearance_template.events import from_stored
from cora.safety.aggregates.clearance_template.evolver import fold
from cora.safety.aggregates.clearance_template.state import ClearanceTemplate

_STREAM_TYPE = "ClearanceTemplate"


async def load_clearance_template(
    event_store: EventStore,
    template_id: UUID,
) -> ClearanceTemplate | None:
    """Load and fold a ClearanceTemplate's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, template_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


__all__ = ["load_clearance_template"]
