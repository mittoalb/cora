"""Pure decider for the `StartCampaign` command.

Single-source transition: `Planned -> Active`. Strict-not-idempotent
(re-starting an already-Active Campaign raises).

## Validation

  - State must not be None -> `CampaignNotFoundError`
  - Current status must be `Planned` -> `CampaignCannotStartError`
"""

from datetime import datetime

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotStartError,
    CampaignNotFoundError,
    CampaignStarted,
    CampaignStatus,
)
from cora.campaign.features.start_campaign.command import StartCampaign

_STARTABLE_STATUSES: tuple[CampaignStatus, ...] = (CampaignStatus.PLANNED,)


def decide(
    state: Campaign | None,
    command: StartCampaign,
    *,
    now: datetime,
) -> list[CampaignStarted]:
    """Decide the events produced by starting a Planned Campaign.

    Invariants:
      - State must not be None -> CampaignNotFoundError
      - Current status must be Planned -> CampaignCannotStartError
    """
    if state is None:
        raise CampaignNotFoundError(command.campaign_id)
    if state.status not in _STARTABLE_STATUSES:
        raise CampaignCannotStartError(state.id, state.status)

    return [CampaignStarted(campaign_id=state.id, occurred_at=now)]
