"""Application-handler tests for `hold_campaign` slice."""

import pytest

from cora.campaign.aggregates.campaign import (
    CampaignNotFoundError,
    CampaignStatus,
    fold,
    from_stored,
)
from cora.campaign.features import hold_campaign
from cora.campaign.features.hold_campaign import HoldCampaign
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.campaign._helpers import (
    CAMPAIGN_ID,
    CORRELATION_ID,
    NOW,
    PRINCIPAL_ID,
    TRANSITION_EVENT_ID,
    seed_active,
)


@pytest.mark.unit
async def test_handler_holds_active_campaign_with_reason() -> None:
    store = InMemoryEventStore()
    await seed_active(store)
    deps = _build_deps_shared(
        ids=[TRANSITION_EVENT_ID],
        now=NOW,
        event_store=store,
    )
    handler = hold_campaign.bind(deps)
    await handler(
        HoldCampaign(campaign_id=CAMPAIGN_ID, reason="beam interruption"),
        principal_id=PRINCIPAL_ID,
        correlation_id=CORRELATION_ID,
    )
    stored, _ = await store.load("Campaign", CAMPAIGN_ID)
    state = fold([from_stored(s) for s in stored])
    assert state is not None
    assert state.status == CampaignStatus.HELD
    assert state.last_status_reason == "beam interruption"


@pytest.mark.unit
async def test_handler_raises_not_found_when_campaign_missing() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(
        ids=[TRANSITION_EVENT_ID],
        now=NOW,
        event_store=store,
    )
    handler = hold_campaign.bind(deps)
    with pytest.raises(CampaignNotFoundError):
        await handler(
            HoldCampaign(campaign_id=CAMPAIGN_ID, reason="r"),
            principal_id=PRINCIPAL_ID,
            correlation_id=CORRELATION_ID,
        )
