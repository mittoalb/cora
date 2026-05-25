"""Application-handler tests for `start_campaign` slice.

The handler is a 7-line `bind` over `make_campaign_update_handler`
(which delegates to the cross-BC `make_update_handler`). Tests
verify factory wiring + envelope plumbing; the factory body itself
is exercised by Supply / Safety transition tests + infrastructure
tests.
"""

import pytest

from cora.campaign.aggregates.campaign import (
    CampaignNotFoundError,
    CampaignStatus,
    fold,
    from_stored,
)
from cora.campaign.features import start_campaign
from cora.campaign.features.start_campaign import StartCampaign
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.campaign._helpers import (
    CAMPAIGN_ID,
    CORRELATION_ID,
    NOW,
    PRINCIPAL_ID,
    TRANSITION_EVENT_ID,
    seed_planned,
)


@pytest.mark.unit
async def test_handler_starts_planned_campaign() -> None:
    store = InMemoryEventStore()
    await seed_planned(store)
    deps = _build_deps_shared(
        ids=[TRANSITION_EVENT_ID],
        now=NOW,
        event_store=store,
    )
    handler = start_campaign.bind(deps)
    await handler(
        StartCampaign(campaign_id=CAMPAIGN_ID),
        principal_id=PRINCIPAL_ID,
        correlation_id=CORRELATION_ID,
    )
    stored, _ = await store.load("Campaign", CAMPAIGN_ID)
    state = fold([from_stored(s) for s in stored])
    assert state is not None
    assert state.status == CampaignStatus.ACTIVE


@pytest.mark.unit
async def test_handler_raises_not_found_when_campaign_missing() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(
        ids=[TRANSITION_EVENT_ID],
        now=NOW,
        event_store=store,
    )
    handler = start_campaign.bind(deps)
    with pytest.raises(CampaignNotFoundError):
        await handler(
            StartCampaign(campaign_id=CAMPAIGN_ID),
            principal_id=PRINCIPAL_ID,
            correlation_id=CORRELATION_ID,
        )
