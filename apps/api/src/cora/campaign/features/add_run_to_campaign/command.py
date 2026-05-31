"""The `AddRunToCampaign` command -- intent dataclass for this slice.

Adds a Run as a member of a Campaign in a non-terminal status (Planned
/ Active / Held). Atomic two-stream write via `EventStore.append_streams`:

  - Campaign stream gets `CampaignRunAdded(campaign_id, run_id, ...)`
  - Run stream gets `RunAddedToCampaign(run_id, campaign_id, ...)`

Both writes commit together or roll back together per the
multi-stream OCC contract (same shape as Safety's `amend_clearance`).

The transitioning actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command / events.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AddRunToCampaign:
    """Add a Run as a member of a Campaign (cross-aggregate atomic).

    Both ids are required. The handler pre-loads both aggregates and the
    decider validates the cross-aggregate invariants (Campaign in a
    membership-eligible status, Run not already in this Campaign, Run
    not already in a DIFFERENT Campaign) before returning the two event
    lists for the atomic `append_streams` write.
    """

    campaign_id: UUID
    run_id: UUID
