"""Decider tests for `resume_campaign` slice (Held -> Active)."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotResumeError,
    CampaignIntent,
    CampaignName,
    CampaignNotFoundError,
    CampaignResumed,
    CampaignStatus,
)
from cora.campaign.features.resume_campaign import ResumeCampaign
from cora.campaign.features.resume_campaign.decider import decide

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000090001")
_LEAD = UUID("01900000-0000-7000-8000-000000090099")


def _campaign(status: CampaignStatus) -> Campaign:
    return Campaign(
        id=_CAMPAIGN_ID,
        name=CampaignName("test"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD,
        status=status,
    )


@pytest.mark.unit
def test_decider_emits_resumed_event_when_held() -> None:
    events = decide(
        state=_campaign(CampaignStatus.HELD),
        command=ResumeCampaign(campaign_id=_CAMPAIGN_ID),
        now=_NOW,
    )
    assert len(events) == 1
    [event] = events
    assert isinstance(event, CampaignResumed)
    assert event.campaign_id == _CAMPAIGN_ID
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decider_raises_not_found_on_empty_state() -> None:
    with pytest.raises(CampaignNotFoundError):
        decide(
            state=None,
            command=ResumeCampaign(campaign_id=_CAMPAIGN_ID),
            now=_NOW,
        )


@pytest.mark.parametrize(
    "current_status",
    [
        CampaignStatus.PLANNED,
        CampaignStatus.ACTIVE,
        CampaignStatus.CLOSED,
        CampaignStatus.ABANDONED,
    ],
)
@pytest.mark.unit
def test_decider_rejects_non_held_statuses(current_status: CampaignStatus) -> None:
    with pytest.raises(CampaignCannotResumeError) as exc_info:
        decide(
            state=_campaign(current_status),
            command=ResumeCampaign(campaign_id=_CAMPAIGN_ID),
            now=_NOW,
        )
    assert exc_info.value.current_status == current_status
