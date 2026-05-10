"""Read repository for the Policy aggregate.

`load_policy(event_store, policy_id) -> Policy | None` mirrors
`load_zone` / `load_conduit`. Used by the eventual evaluate_policy
query slice (Phase 3d) and by `TrustAuthorize` (Phase 3e).
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.trust.aggregates.policy.events import from_stored
from cora.trust.aggregates.policy.evolver import fold
from cora.trust.aggregates.policy.state import Policy

_STREAM_TYPE = "Policy"


async def load_policy(event_store: EventStore, policy_id: UUID) -> Policy | None:
    """Load and fold a Policy's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, policy_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
