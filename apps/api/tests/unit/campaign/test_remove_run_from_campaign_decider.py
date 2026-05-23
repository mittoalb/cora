"""Unit tests for the `remove_run_from_campaign` cross-aggregate decider.

Pins validation order + happy-path event-pair shape. Mirrors
`add_run_to_campaign` decider's test style.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotRemoveRunError,
    CampaignIntent,
    CampaignName,
    CampaignRunNotMemberError,
    CampaignRunRemoved,
    CampaignStatus,
    InvalidCampaignRunRemoveReasonError,
)
from cora.campaign.features.remove_run_from_campaign import decide
from cora.campaign.features.remove_run_from_campaign.command import RemoveRunFromCampaign
from cora.campaign.features.remove_run_from_campaign.context import (
    CampaignMembershipContext,
)
from cora.run.aggregates.run import (
    Run,
    RunCampaignUnassigned,
    RunName,
    RunStatus,
)

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000d00001")
_RUN_ID = UUID("01900000-0000-7000-8000-000000d00002")
_LEAD = UUID("01900000-0000-7000-8000-000000d000aa")
_PLAN = UUID("01900000-0000-7000-8000-000000d000bb")


def _campaign(status: CampaignStatus, run_ids: frozenset[UUID] | None = None) -> Campaign:
    return Campaign(
        id=_CAMPAIGN_ID,
        name=CampaignName("test"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD,
        status=status,
        run_ids=run_ids if run_ids is not None else frozenset({_RUN_ID}),
    )


def _run() -> Run:
    return Run(
        id=_RUN_ID,
        name=RunName("test"),
        plan_id=_PLAN,
        subject_id=None,
        status=RunStatus.RUNNING,
        campaign_id=_CAMPAIGN_ID,
    )


def _context(campaign: Campaign, run: Run) -> CampaignMembershipContext:
    return CampaignMembershipContext(
        campaign=campaign,
        campaign_version=3,
        run=run,
        run_version=2,
    )


def _cmd(reason: str = "operator removed") -> RemoveRunFromCampaign:
    return RemoveRunFromCampaign(
        campaign_id=_CAMPAIGN_ID,
        run_id=_RUN_ID,
        reason=reason,
    )


# ---------- Happy path ----------


@pytest.mark.unit
def test_remove_run_returns_paired_events_on_happy_path() -> None:
    campaign = _campaign(CampaignStatus.ACTIVE)
    run = _run()
    events = decide(state=campaign, command=_cmd(), context=_context(campaign, run), now=_NOW)
    assert events.campaign_events == [
        CampaignRunRemoved(
            campaign_id=_CAMPAIGN_ID,
            run_id=_RUN_ID,
            reason="operator removed",
            occurred_at=_NOW,
        )
    ]
    assert events.run_events == [
        RunCampaignUnassigned(
            run_id=_RUN_ID,
            campaign_id=_CAMPAIGN_ID,
            reason="operator removed",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_remove_run_trims_reason() -> None:
    campaign = _campaign(CampaignStatus.ACTIVE)
    run = _run()
    events = decide(
        state=campaign,
        command=_cmd(reason="   removed   "),
        context=_context(campaign, run),
        now=_NOW,
    )
    assert events.campaign_events[0].reason == "removed"
    assert events.run_events[0].reason == "removed"


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [CampaignStatus.PLANNED, CampaignStatus.ACTIVE, CampaignStatus.HELD],
)
def test_remove_run_accepts_each_membership_eligible_status(status: CampaignStatus) -> None:
    campaign = _campaign(status)
    run = _run()
    events = decide(state=campaign, command=_cmd(), context=_context(campaign, run), now=_NOW)
    assert len(events.campaign_events) == 1


# ---------- Terminal-Campaign guard ----------


@pytest.mark.unit
@pytest.mark.parametrize("status", [CampaignStatus.CLOSED, CampaignStatus.ABANDONED])
def test_remove_run_rejects_terminal_campaign(status: CampaignStatus) -> None:
    campaign = _campaign(status)
    run = _run()
    with pytest.raises(CampaignCannotRemoveRunError) as exc:
        decide(state=campaign, command=_cmd(), context=_context(campaign, run), now=_NOW)
    assert exc.value.current_status == status


# ---------- Not-a-member guard ----------


@pytest.mark.unit
def test_remove_run_rejects_when_run_not_member() -> None:
    campaign = _campaign(CampaignStatus.ACTIVE, run_ids=frozenset())
    run = _run()
    with pytest.raises(CampaignRunNotMemberError) as exc:
        decide(state=campaign, command=_cmd(), context=_context(campaign, run), now=_NOW)
    assert exc.value.run_id == _RUN_ID


# ---------- Reason validation ----------


@pytest.mark.unit
def test_remove_run_rejects_empty_reason() -> None:
    campaign = _campaign(CampaignStatus.ACTIVE)
    run = _run()
    with pytest.raises(InvalidCampaignRunRemoveReasonError):
        decide(
            state=campaign,
            command=_cmd(reason="   "),
            context=_context(campaign, run),
            now=_NOW,
        )


@pytest.mark.unit
def test_remove_run_rejects_too_long_reason() -> None:
    campaign = _campaign(CampaignStatus.ACTIVE)
    run = _run()
    with pytest.raises(InvalidCampaignRunRemoveReasonError):
        decide(
            state=campaign,
            command=_cmd(reason="x" * 501),
            context=_context(campaign, run),
            now=_NOW,
        )
