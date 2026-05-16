"""Read repository for the Campaign aggregate.

`load_campaign(event_store, campaign_id) -> Campaign | None` mirrors
`load_caution` / `load_supply` / `load_clearance` / `load_asset`.
Used by the `get_campaign` query slice. The transition slices use
the cross-BC `make_update_handler` factory (via Campaign's
`_campaign_update_handler` thin wrapper), which does its own
load-then-fold internally.
"""

from uuid import UUID

from cora.campaign.aggregates.campaign.events import from_stored
from cora.campaign.aggregates.campaign.evolver import fold
from cora.campaign.aggregates.campaign.state import Campaign
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Campaign"


async def load_campaign(event_store: EventStore, campaign_id: UUID) -> Campaign | None:
    """Load and fold a Campaign's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, campaign_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
