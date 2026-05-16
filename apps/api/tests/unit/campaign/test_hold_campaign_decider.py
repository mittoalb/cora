"""Decider tests for `hold_campaign` slice (Active -> Held; reason required)."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotHoldError,
    CampaignHeld,
    CampaignIntent,
    CampaignName,
    CampaignNotFoundError,
    CampaignStatus,
    InvalidCampaignHoldReasonError,
)
from cora.campaign.features.hold_campaign import HoldCampaign
from cora.campaign.features.hold_campaign.decider import decide

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000080001")
_LEAD = UUID("01900000-0000-7000-8000-000000080099")


def _campaign(status: CampaignStatus) -> Campaign:
    return Campaign(
        id=_CAMPAIGN_ID,
        name=CampaignName("test"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD,
        status=status,
    )


@pytest.mark.unit
def test_decider_emits_held_event_when_active() -> None:
    events = decide(
        state=_campaign(CampaignStatus.ACTIVE),
        command=HoldCampaign(campaign_id=_CAMPAIGN_ID, reason="beam interruption"),
        now=_NOW,
    )
    assert len(events) == 1
    [event] = events
    assert isinstance(event, CampaignHeld)
    assert event.reason == "beam interruption"
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decider_trims_reason() -> None:
    events = decide(
        state=_campaign(CampaignStatus.ACTIVE),
        command=HoldCampaign(campaign_id=_CAMPAIGN_ID, reason="  trimmed  "),
        now=_NOW,
    )
    assert events[0].reason == "trimmed"


@pytest.mark.unit
def test_decider_rejects_empty_reason() -> None:
    with pytest.raises(InvalidCampaignHoldReasonError):
        decide(
            state=_campaign(CampaignStatus.ACTIVE),
            command=HoldCampaign(campaign_id=_CAMPAIGN_ID, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decider_rejects_too_long_reason() -> None:
    with pytest.raises(InvalidCampaignHoldReasonError):
        decide(
            state=_campaign(CampaignStatus.ACTIVE),
            command=HoldCampaign(campaign_id=_CAMPAIGN_ID, reason="a" * 501),
            now=_NOW,
        )


@pytest.mark.unit
def test_decider_raises_not_found_on_empty_state() -> None:
    with pytest.raises(CampaignNotFoundError):
        decide(
            state=None,
            command=HoldCampaign(campaign_id=_CAMPAIGN_ID, reason="r"),
            now=_NOW,
        )


@pytest.mark.parametrize(
    "current_status",
    [
        CampaignStatus.PLANNED,
        CampaignStatus.HELD,
        CampaignStatus.CLOSED,
        CampaignStatus.ABANDONED,
    ],
)
@pytest.mark.unit
def test_decider_rejects_non_active_statuses(current_status: CampaignStatus) -> None:
    with pytest.raises(CampaignCannotHoldError) as exc_info:
        decide(
            state=_campaign(current_status),
            command=HoldCampaign(campaign_id=_CAMPAIGN_ID, reason="r"),
            now=_NOW,
        )
    assert exc_info.value.current_status == current_status
