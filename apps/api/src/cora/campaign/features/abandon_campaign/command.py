"""The `AbandonCampaign` command -- intent dataclass for this slice.

Transitions a non-terminal Campaign to Abandoned (early terminal
with reason). Multi-source from {Planned, Active, Held}. Members
are locked after this transition. `reason: str` is REQUIRED (1-500
chars validated at decider; mirrors `RunAbortReason` REQUIRED-on-
abort precedent).

The abandoning actor's identity lives on the event envelope.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AbandonCampaign:
    """Abandon a non-terminal Campaign (`Planned | Active | Held -> Abandoned`)."""

    campaign_id: UUID
    reason: str
