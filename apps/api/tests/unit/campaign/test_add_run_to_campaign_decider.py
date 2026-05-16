"""Unit tests for the `add_run_to_campaign` cross-aggregate decider.

Pins the decider's validation order + happy-path event-pair shape.
Mirrors `amend_clearance` decider's test style (cross-aggregate
state + two-event-list return). Phase 6i-c.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotAddRunError,
    CampaignIntent,
    CampaignName,
    CampaignRunAdded,
    CampaignRunAlreadyMemberError,
    CampaignStatus,
)
from cora.campaign.features.add_run_to_campaign import decide
from cora.campaign.features.add_run_to_campaign.command import AddRunToCampaign
from cora.campaign.features.add_run_to_campaign.context import CampaignMembershipContext
from cora.run.aggregates.run import (
    Run,
    RunAlreadyAssignedToCampaignError,
    RunCampaignAssigned,
    RunName,
    RunStatus,
)

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000c00001")
_RUN_ID = UUID("01900000-0000-7000-8000-000000c00002")
_OTHER_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000c00099")
_LEAD = UUID("01900000-0000-7000-8000-000000c000aa")
_PLAN = UUID("01900000-0000-7000-8000-000000c000bb")


def _campaign(status: CampaignStatus, run_ids: frozenset[UUID] | None = None) -> Campaign:
    return Campaign(
        id=_CAMPAIGN_ID,
        name=CampaignName("test"),
        intent=CampaignIntent.IN_SITU,
        lead_actor_id=_LEAD,
        status=status,
        run_ids=run_ids or frozenset(),
    )


def _run(campaign_id: UUID | None = None) -> Run:
    return Run(
        id=_RUN_ID,
        name=RunName("test"),
        plan_id=_PLAN,
        subject_id=None,
        status=RunStatus.RUNNING,
        campaign_id=campaign_id,
    )


def _context(campaign: Campaign, run: Run) -> CampaignMembershipContext:
    return CampaignMembershipContext(
        campaign=campaign,
        campaign_version=2,
        run=run,
        run_version=1,
    )


def _cmd() -> AddRunToCampaign:
    return AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID)


# ---------- Happy path ----------


@pytest.mark.unit
def test_add_run_returns_paired_events_on_happy_path() -> None:
    campaign = _campaign(CampaignStatus.ACTIVE)
    run = _run()
    events = decide(state=campaign, command=_cmd(), context=_context(campaign, run), now=_NOW)
    assert events.campaign_events == [
        CampaignRunAdded(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID, occurred_at=_NOW)
    ]
    assert events.run_events == [
        RunCampaignAssigned(run_id=_RUN_ID, campaign_id=_CAMPAIGN_ID, occurred_at=_NOW)
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [CampaignStatus.PLANNED, CampaignStatus.ACTIVE, CampaignStatus.HELD],
)
def test_add_run_accepts_each_membership_eligible_status(status: CampaignStatus) -> None:
    campaign = _campaign(status)
    run = _run()
    events = decide(state=campaign, command=_cmd(), context=_context(campaign, run), now=_NOW)
    assert len(events.campaign_events) == 1
    assert len(events.run_events) == 1


# ---------- Terminal-Campaign guard ----------


@pytest.mark.unit
@pytest.mark.parametrize("status", [CampaignStatus.CLOSED, CampaignStatus.ABANDONED])
def test_add_run_rejects_terminal_campaign(status: CampaignStatus) -> None:
    campaign = _campaign(status)
    run = _run()
    with pytest.raises(CampaignCannotAddRunError) as exc:
        decide(state=campaign, command=_cmd(), context=_context(campaign, run), now=_NOW)
    assert exc.value.current_status == status


# ---------- Idempotency guard ----------


@pytest.mark.unit
def test_add_run_rejects_already_member() -> None:
    campaign = _campaign(CampaignStatus.ACTIVE, run_ids=frozenset({_RUN_ID}))
    run = _run()
    with pytest.raises(CampaignRunAlreadyMemberError) as exc:
        decide(state=campaign, command=_cmd(), context=_context(campaign, run), now=_NOW)
    assert exc.value.run_id == _RUN_ID


# ---------- One-Campaign-per-Run guard ----------


@pytest.mark.unit
def test_add_run_rejects_run_assigned_to_different_campaign() -> None:
    campaign = _campaign(CampaignStatus.ACTIVE)
    run = _run(campaign_id=_OTHER_CAMPAIGN_ID)
    with pytest.raises(RunAlreadyAssignedToCampaignError) as exc:
        decide(state=campaign, command=_cmd(), context=_context(campaign, run), now=_NOW)
    assert exc.value.existing_campaign_id == _OTHER_CAMPAIGN_ID
    assert exc.value.new_campaign_id == _CAMPAIGN_ID


@pytest.mark.unit
def test_add_run_accepts_run_already_assigned_to_same_campaign() -> None:
    """Run.campaign_id equal to the target Campaign means the Run was
    already at-start-bound to this Campaign via StartRun.campaign_id
    (and the Campaign's run_ids must show it for the add to be
    well-formed). If the Run is NOT in run_ids but carries
    campaign_id=this_campaign, we treat that as a divergent state
    that the membership-idempotency guard catches first; this test
    pins that the one-Campaign-per-Run check does NOT misfire on the
    same-campaign case."""
    campaign = _campaign(CampaignStatus.ACTIVE)
    run = _run(campaign_id=_CAMPAIGN_ID)
    # Run is not in run_ids but carries our own campaign_id (divergent
    # data); the same-id check passes, so we hit the run-not-member
    # path differently. Here we only assert the same-id branch does
    # NOT raise RunAlreadyAssignedToCampaignError; we expect the
    # happy-path return.
    events = decide(state=campaign, command=_cmd(), context=_context(campaign, run), now=_NOW)
    assert len(events.campaign_events) == 1
