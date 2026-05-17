"""Read repository for the Agent aggregate.

`load_agent(event_store, agent_id) -> Agent | None` mirrors
`load_actor` / `load_caution` / `load_supply`. Used by the
`get_agent` query slice and the update-style handlers
(`version_agent` and `deprecate_agent` load the target Agent before
the decider).
"""

from uuid import UUID

from cora.agent.aggregates.agent.events import from_stored
from cora.agent.aggregates.agent.evolver import fold
from cora.agent.aggregates.agent.state import Agent
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Agent"


async def load_agent(event_store: EventStore, agent_id: UUID) -> Agent | None:
    """Load and fold an Agent's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, agent_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
