"""Pure decider for the `ResumeCampaign` command.

Single-source transition: `Held -> Active`. Strict-not-idempotent
(re-resuming an already-Active Campaign raises).

## Validation

  - State must not be None -> `CampaignNotFoundError`
  - Current status must be `Held` -> `CampaignCannotResumeError`
"""

from datetime import datetime

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotResumeError,
    CampaignNotFoundError,
    CampaignResumed,
    CampaignStatus,
)
from cora.campaign.features.resume_campaign.command import ResumeCampaign

_RESUMABLE_STATUSES: tuple[CampaignStatus, ...] = (CampaignStatus.HELD,)


def decide(
    state: Campaign | None,
    command: ResumeCampaign,
    *,
    now: datetime,
) -> list[CampaignResumed]:
    """Decide the events produced by resuming a Held Campaign."""
    if state is None:
        raise CampaignNotFoundError(command.campaign_id)
    if state.status not in _RESUMABLE_STATUSES:
        raise CampaignCannotResumeError(state.id, state.status)

    return [CampaignResumed(campaign_id=state.id, occurred_at=now)]
