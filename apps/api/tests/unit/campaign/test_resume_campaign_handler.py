"""Application-handler tests for `resume_campaign` slice."""

import pytest

from cora.campaign.aggregates.campaign import (
    CampaignNotFoundError,
    CampaignStatus,
    fold,
    from_stored,
)
from cora.campaign.features import resume_campaign
from cora.campaign.features.resume_campaign import ResumeCampaign
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.campaign._transition_helpers import (
    CAMPAIGN_ID,
    CORRELATION_ID,
    NOW,
    PRINCIPAL_ID,
    TRANSITION_EVENT_ID,
    seed_held,
)


@pytest.mark.unit
async def test_handler_resumes_held_campaign_and_preserves_reason() -> None:
    store = InMemoryEventStore()
    await seed_held(store)
    deps = _build_deps_shared(
        ids=[TRANSITION_EVENT_ID],
        now=NOW,
        event_store=store,
    )
    handler = resume_campaign.bind(deps)
    await handler(
        ResumeCampaign(campaign_id=CAMPAIGN_ID),
        principal_id=PRINCIPAL_ID,
        correlation_id=CORRELATION_ID,
    )
    stored, _ = await store.load("Campaign", CAMPAIGN_ID)
    state = fold([from_stored(s) for s in stored])
    assert state is not None
    assert state.status == CampaignStatus.ACTIVE
    # Held reason is preserved across resume (audit breadcrumb).
    assert state.last_status_reason == "seed reason"


@pytest.mark.unit
async def test_handler_raises_not_found_when_campaign_missing() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(
        ids=[TRANSITION_EVENT_ID],
        now=NOW,
        event_store=store,
    )
    handler = resume_campaign.bind(deps)
    with pytest.raises(CampaignNotFoundError):
        await handler(
            ResumeCampaign(campaign_id=CAMPAIGN_ID),
            principal_id=PRINCIPAL_ID,
            correlation_id=CORRELATION_ID,
        )
