"""The `CloseCampaign` command -- intent dataclass for this slice.

Transitions an Active or Held Campaign to Closed (normal terminal).
Multi-source from {Active, Held}. Members are locked after this
transition. No reason field (normal terminal; mirrors Run
`Completed` semantic).

The closing actor's identity lives on the event envelope.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CloseCampaign:
    """Close a Campaign (`Active | Held -> Closed`)."""

    campaign_id: UUID
