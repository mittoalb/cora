"""Read repository for the Plan aggregate.

`load_plan(event_store, plan_id) -> Plan | None` mirrors
`load_practice` / `load_method` / `load_capability` / `load_actor` /
etc. Used by the `get_plan` query slice (6e-1) and any future
update-style commands (6e-2).
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.recipe.aggregates.plan.events import from_stored
from cora.recipe.aggregates.plan.evolver import fold
from cora.recipe.aggregates.plan.state import Plan

_STREAM_TYPE = "Plan"


async def load_plan(event_store: EventStore, plan_id: UUID) -> Plan | None:
    """Load and fold a Plan's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, plan_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
