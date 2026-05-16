"""Decider tests for `close_campaign` slice ({Active, Held} -> Closed)."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotCloseError,
    CampaignClosed,
    CampaignIntent,
    CampaignName,
    CampaignNotFoundError,
    CampaignStatus,
)
from cora.campaign.features.close_campaign import CloseCampaign
from cora.campaign.features.close_campaign.decider import decide

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-0000000a0001")
_LEAD = UUID("01900000-0000-7000-8000-0000000a0099")


def _campaign(status: CampaignStatus) -> Campaign:
    return Campaign(
        id=_CAMPAIGN_ID,
        name=CampaignName("test"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD,
        status=status,
    )


@pytest.mark.parametrize("source_status", [CampaignStatus.ACTIVE, CampaignStatus.HELD])
@pytest.mark.unit
def test_decider_emits_closed_event_from_active_or_held(
    source_status: CampaignStatus,
) -> None:
    events = decide(
        state=_campaign(source_status),
        command=CloseCampaign(campaign_id=_CAMPAIGN_ID),
        now=_NOW,
    )
    assert len(events) == 1
    [event] = events
    assert isinstance(event, CampaignClosed)
    assert event.campaign_id == _CAMPAIGN_ID
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decider_raises_not_found_on_empty_state() -> None:
    with pytest.raises(CampaignNotFoundError):
        decide(
            state=None,
            command=CloseCampaign(campaign_id=_CAMPAIGN_ID),
            now=_NOW,
        )


@pytest.mark.parametrize(
    "current_status",
    [
        CampaignStatus.PLANNED,
        CampaignStatus.CLOSED,
        CampaignStatus.ABANDONED,
    ],
)
@pytest.mark.unit
def test_decider_rejects_non_closable_statuses(current_status: CampaignStatus) -> None:
    with pytest.raises(CampaignCannotCloseError) as exc_info:
        decide(
            state=_campaign(current_status),
            command=CloseCampaign(campaign_id=_CAMPAIGN_ID),
            now=_NOW,
        )
    assert exc_info.value.current_status == current_status
