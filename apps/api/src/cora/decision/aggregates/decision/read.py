"""Read repository for the Decision aggregate.

`load_decision(event_store, decision_id) -> Decision | None`
mirrors `load_actor` / `load_subject` / `load_run` / etc.

The aggregate is atomic-immutable, so a load returns either the
single-event genesis state or None. Chain navigation (walking
`parent_id` to reconstruct correction history) is a projection
concern, not part of the aggregate read.
"""

from uuid import UUID

from cora.decision.aggregates.decision.events import from_stored
from cora.decision.aggregates.decision.evolver import fold
from cora.decision.aggregates.decision.state import Decision
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Decision"


async def load_decision(event_store: EventStore, decision_id: UUID) -> Decision | None:
    """Load and fold a Decision's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, decision_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
