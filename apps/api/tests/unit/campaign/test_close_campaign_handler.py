"""Application-handler tests for `close_campaign` slice."""

import pytest

from cora.campaign.aggregates.campaign import (
    CampaignNotFoundError,
    CampaignStatus,
    fold,
    from_stored,
)
from cora.campaign.features import close_campaign
from cora.campaign.features.close_campaign import CloseCampaign
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.campaign._transition_helpers import (
    CAMPAIGN_ID,
    CORRELATION_ID,
    NOW,
    PRINCIPAL_ID,
    TRANSITION_EVENT_ID,
    seed_active,
)


@pytest.mark.unit
async def test_handler_closes_active_campaign() -> None:
    store = InMemoryEventStore()
    await seed_active(store)
    deps = _build_deps_shared(
        ids=[TRANSITION_EVENT_ID],
        now=NOW,
        event_store=store,
    )
    handler = close_campaign.bind(deps)
    await handler(
        CloseCampaign(campaign_id=CAMPAIGN_ID),
        principal_id=PRINCIPAL_ID,
        correlation_id=CORRELATION_ID,
    )
    stored, _ = await store.load("Campaign", CAMPAIGN_ID)
    state = fold([from_stored(s) for s in stored])
    assert state is not None
    assert state.status == CampaignStatus.CLOSED


@pytest.mark.unit
async def test_handler_raises_not_found_when_campaign_missing() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(
        ids=[TRANSITION_EVENT_ID],
        now=NOW,
        event_store=store,
    )
    handler = close_campaign.bind(deps)
    with pytest.raises(CampaignNotFoundError):
        await handler(
            CloseCampaign(campaign_id=CAMPAIGN_ID),
            principal_id=PRINCIPAL_ID,
            correlation_id=CORRELATION_ID,
        )
