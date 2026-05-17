"""The `ReviseAgentBudget` command -- intent dataclass for this slice.

Carries the FULL desired post-revision budget shape (PUT semantics,
not PATCH): the revised budget IS the supplied caps, not a merge
with the prior values. When both `monthly_usd_cap` and
`daily_token_cap` are None the Agent's `budget` is cleared.

The revising actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ReviseAgentBudget:
    """Revise an Agent's declarative budget caps (PUT semantics)."""

    agent_id: UUID
    monthly_usd_cap: float | None
    daily_token_cap: int | None
