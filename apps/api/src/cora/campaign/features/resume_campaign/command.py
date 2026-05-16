"""The `ResumeCampaign` command -- intent dataclass for this slice.

Transitions a Held Campaign back to Active. Single-source from Held.
Carries no operator fields beyond the target id (resume is just
"permission to proceed"; the prior Held reason is preserved on the
aggregate so the audit chain stays readable).

The resuming actor's identity lives on the event envelope.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ResumeCampaign:
    """Resume a Held Campaign (`Held -> Active`)."""

    campaign_id: UUID
