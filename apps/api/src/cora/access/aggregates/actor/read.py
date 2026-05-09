"""Read repository for the Actor aggregate.

Single function: `load_actor(event_store, actor_id) -> Actor | None`
loads the aggregate's stream from the EventStore, deserializes via
`from_stored`, and folds with the evolver to produce current state.

Sits with the aggregate (not the slice) because it operates on the
aggregate's stream regardless of which command produced the events.
Queries across multiple aggregates would live in a different module
(deferred until needed).

Phase 2b uses fold-on-read for single-aggregate GETs. List/filter/search
endpoints (when they land) will need a projection-worker pattern with
a denormalized table; fold-on-read scales O(events-per-stream) per read
and doesn't support cross-aggregate queries efficiently.
"""

from uuid import UUID

from cora.access.aggregates.actor.events import from_stored
from cora.access.aggregates.actor.evolver import fold
from cora.access.aggregates.actor.state import Actor
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Actor"


async def load_actor(event_store: EventStore, actor_id: UUID) -> Actor | None:
    """Load and fold an Actor's event stream into current state.

    Returns None if the stream has no events (the actor was never
    registered). The caller maps None to whatever is appropriate for
    its surface (HTTP 404, MCP isError, etc.).
    """
    stored, _version = await event_store.load(_STREAM_TYPE, actor_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
