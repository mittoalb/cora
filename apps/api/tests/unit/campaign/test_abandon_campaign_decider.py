"""Decider tests for `abandon_campaign` slice
({Planned, Active, Held} -> Abandoned; reason required).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignAbandoned,
    CampaignCannotAbandonError,
    CampaignIntent,
    CampaignName,
    CampaignNotFoundError,
    CampaignStatus,
    InvalidCampaignAbandonReasonError,
)
from cora.campaign.features.abandon_campaign import AbandonCampaign
from cora.campaign.features.abandon_campaign.decider import decide

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-0000000b0001")
_LEAD = UUID("01900000-0000-7000-8000-0000000b0099")


def _campaign(status: CampaignStatus) -> Campaign:
    return Campaign(
        id=_CAMPAIGN_ID,
        name=CampaignName("test"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD,
        status=status,
    )


@pytest.mark.parametrize(
    "source_status",
    [CampaignStatus.PLANNED, CampaignStatus.ACTIVE, CampaignStatus.HELD],
)
@pytest.mark.unit
def test_decider_emits_abandoned_event_from_non_terminal(
    source_status: CampaignStatus,
) -> None:
    events = decide(
        state=_campaign(source_status),
        command=AbandonCampaign(
            campaign_id=_CAMPAIGN_ID,
            reason="instrument failure",
        ),
        now=_NOW,
    )
    assert len(events) == 1
    [event] = events
    assert isinstance(event, CampaignAbandoned)
    assert event.reason == "instrument failure"
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decider_trims_reason() -> None:
    events = decide(
        state=_campaign(CampaignStatus.ACTIVE),
        command=AbandonCampaign(campaign_id=_CAMPAIGN_ID, reason="  trimmed  "),
        now=_NOW,
    )
    assert events[0].reason == "trimmed"


@pytest.mark.unit
def test_decider_rejects_empty_reason() -> None:
    with pytest.raises(InvalidCampaignAbandonReasonError):
        decide(
            state=_campaign(CampaignStatus.ACTIVE),
            command=AbandonCampaign(campaign_id=_CAMPAIGN_ID, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decider_rejects_too_long_reason() -> None:
    with pytest.raises(InvalidCampaignAbandonReasonError):
        decide(
            state=_campaign(CampaignStatus.ACTIVE),
            command=AbandonCampaign(campaign_id=_CAMPAIGN_ID, reason="a" * 501),
            now=_NOW,
        )


@pytest.mark.unit
def test_decider_raises_not_found_on_empty_state() -> None:
    with pytest.raises(CampaignNotFoundError):
        decide(
            state=None,
            command=AbandonCampaign(campaign_id=_CAMPAIGN_ID, reason="r"),
            now=_NOW,
        )


@pytest.mark.parametrize(
    "current_status",
    [
        CampaignStatus.CLOSED,
        CampaignStatus.ABANDONED,
    ],
)
@pytest.mark.unit
def test_decider_rejects_terminal_statuses(current_status: CampaignStatus) -> None:
    with pytest.raises(CampaignCannotAbandonError) as exc_info:
        decide(
            state=_campaign(current_status),
            command=AbandonCampaign(campaign_id=_CAMPAIGN_ID, reason="r"),
            now=_NOW,
        )
    assert exc_info.value.current_status == current_status
