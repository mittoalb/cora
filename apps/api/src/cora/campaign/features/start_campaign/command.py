"""The `StartCampaign` command -- intent dataclass for this slice.

Transitions a Planned Campaign to Active. Single-source from Planned.

The starting actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StartCampaign:
    """Start a Planned Campaign (`Planned -> Active`)."""

    campaign_id: UUID
