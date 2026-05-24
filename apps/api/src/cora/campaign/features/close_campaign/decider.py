"""Pure decider for the `CloseCampaign` command.

Multi-source transition: `{Active, Held} -> Closed`. Strict-not-
idempotent (re-closing a Closed Campaign raises; Abandoned also
refuses).

## Validation

  - State must not be None -> `CampaignNotFoundError`
  - Current status must be in `{Active, Held}` ->
    `CampaignCannotCloseError`

## NO CASCADE

Per Anti-hooks: `close_campaign` writes ONLY to the Campaign stream.
It does NOT modify member Run state. Per GLP §10.2.5, ISO 17025
§7.5, 21 CFR §11.10(e) per-Run audit independence + enterprise
PAS-X cascading-holds war story.
"""

from datetime import datetime

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotCloseError,
    CampaignClosed,
    CampaignNotFoundError,
    CampaignStatus,
)
from cora.campaign.features.close_campaign.command import CloseCampaign

_CLOSABLE_STATUSES: tuple[CampaignStatus, ...] = (
    CampaignStatus.ACTIVE,
    CampaignStatus.HELD,
)


def decide(
    state: Campaign | None,
    command: CloseCampaign,
    *,
    now: datetime,
) -> list[CampaignClosed]:
    """Decide the events produced by closing a Campaign.

    Invariants:
      - State must not be None -> CampaignNotFoundError
      - Current status must be Active or Held
        -> CampaignCannotCloseError
    """
    if state is None:
        raise CampaignNotFoundError(command.campaign_id)
    if state.status not in _CLOSABLE_STATUSES:
        raise CampaignCannotCloseError(state.id, state.status)

    return [CampaignClosed(campaign_id=state.id, occurred_at=now)]
