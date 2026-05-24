"""Pure decider for the `AddRunToCampaign` command.

Cross-aggregate decider: takes a `CampaignMembershipContext` carrying
the loaded Campaign + Run and returns BOTH event lists wrapped in
`MembershipEvents` so the handler doesn't need to guess which stream
gets which event. Atomic two-stream write happens at the handler via
`EventStore.append_streams` (mirrors 11a-c-2 `amend_clearance` shape).

## Validation order

1. Campaign state must not be None -> `CampaignNotFoundError`. The
   handler raises this earlier; the guard here is defensive.
2. Campaign status must be in `{Planned, Active, Held}` ->
   `CampaignCannotAddRunError`. Terminal Campaigns (Closed /
   Abandoned) refuse new members per the design memo lock.
3. Run state must not be None -> `RunNotFoundError`. The handler
   raises this earlier; defensive guard here.
4. Run already in `state.run_ids` -> `CampaignRunAlreadyMemberError`.
   Membership idempotency violation. (Distinct from the next check;
   that's the "different campaign" case.)
5. Run already has a different non-None `campaign_id` ->
   `RunAlreadyAssignedToCampaignError`. One-Campaign-per-Run lock.

If all guards pass, returns `MembershipEvents` carrying:

  - `campaign_events`: `[CampaignRunAdded(campaign_id, run_id, ...)]`
  - `run_events`:      `[RunCampaignAssigned(run_id, campaign_id, ...)]`
"""

from dataclasses import dataclass
from datetime import datetime

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotAddRunError,
    CampaignRunAdded,
    CampaignRunAlreadyMemberError,
    CampaignStatus,
)
from cora.campaign.features.add_run_to_campaign.command import AddRunToCampaign
from cora.campaign.features.add_run_to_campaign.context import CampaignMembershipContext
from cora.run.aggregates.run import (
    RunAlreadyAssignedToCampaignError,
    RunCampaignAssigned,
)

_MEMBERSHIP_ELIGIBLE_STATUSES: tuple[CampaignStatus, ...] = (
    CampaignStatus.PLANNED,
    CampaignStatus.ACTIVE,
    CampaignStatus.HELD,
)


@dataclass(frozen=True)
class MembershipEvents:
    """The two event lists produced by a membership mutation, one per stream.

    `campaign_events`: appended to the Campaign's stream.
    `run_events`: appended to the Run's stream.

    Both lists are non-empty under normal operation; the handler hands
    them to `EventStore.append_streams` as a single atomic batch.
    """

    campaign_events: list[CampaignRunAdded]
    run_events: list[RunCampaignAssigned]


def decide(
    state: Campaign | None,
    command: AddRunToCampaign,
    *,
    context: CampaignMembershipContext,
    now: datetime,
) -> MembershipEvents:
    """Decide the cross-aggregate events produced by adding a Run.

    Invariants:
      - Campaign status must be Planned, Active, or Held
        -> CampaignCannotAddRunError
      - Run must not already be a member of this Campaign
        -> CampaignRunAlreadyMemberError
      - Run must not be assigned to a different Campaign
        -> RunAlreadyAssignedToCampaignError

    `state` is the Campaign's current state (also available on
    `context.campaign`; passed twice mirrors the canonical decider
    signature). The Run state lives on `context.run`.
    """
    _ = state  # context.campaign carries the same Campaign; signature parity.

    # Context types are non-Optional (handler raises Campaign/RunNotFoundError
    # before constructing the context per the amend_clearance precedent).
    campaign = context.campaign
    if campaign.status not in _MEMBERSHIP_ELIGIBLE_STATUSES:
        raise CampaignCannotAddRunError(campaign.id, campaign.status)

    run = context.run

    if command.run_id in campaign.run_ids:
        raise CampaignRunAlreadyMemberError(campaign.id, command.run_id)

    if run.campaign_id is not None and run.campaign_id != command.campaign_id:
        raise RunAlreadyAssignedToCampaignError(
            run_id=run.id,
            existing_campaign_id=run.campaign_id,
            new_campaign_id=command.campaign_id,
        )

    return MembershipEvents(
        campaign_events=[
            CampaignRunAdded(
                campaign_id=campaign.id,
                run_id=command.run_id,
                occurred_at=now,
            )
        ],
        run_events=[
            RunCampaignAssigned(
                run_id=command.run_id,
                campaign_id=campaign.id,
                occurred_at=now,
            )
        ],
    )
