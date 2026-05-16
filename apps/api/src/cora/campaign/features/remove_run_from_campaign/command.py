"""The `RemoveRunFromCampaign` command -- intent dataclass for this slice.

Removes a Run from a Campaign that is in a non-terminal status
(Planned / Active / Held). Atomic two-stream write via
`EventStore.append_streams`:

  - Campaign stream gets `CampaignRunRemoved(campaign_id, run_id,
    reason, ...)`
  - Run stream gets `RunCampaignUnassigned(run_id, campaign_id,
    reason, ...)`

Both writes commit together or roll back together per the 11a-c-2
multi-stream OCC contract.

`reason` is REQUIRED (1-500 chars after trim) per design memo:
ungrouping is meaningful and operators must say why. Lives on both
event payloads as a per-membership audit breadcrumb; does NOT
populate `Campaign.last_status_reason` (that field is for status
transitions only).

The transitioning actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command / events.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RemoveRunFromCampaign:
    """Remove a Run from a Campaign (cross-aggregate atomic).

    `reason` is REQUIRED (free-form audit breadcrumb, 1-500 chars
    after trim). The handler pre-loads both aggregates and the decider
    validates membership preconditions before returning the two event
    lists for the atomic `append_streams` write.
    """

    campaign_id: UUID
    run_id: UUID
    reason: str
