"""The `HoldCampaign` command -- intent dataclass for this slice.

Transitions an Active Campaign to Held. Single-source from Active.
Carries operator-supplied `reason: str` (1-500 chars validated at
the decider; mirrors `RunAbortReason` / `RunStopReason` bare-str
audit-breadcrumb precedent).

The transitioning actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class HoldCampaign:
    """Hold an Active Campaign (`Active -> Held`)."""

    campaign_id: UUID
    reason: str
