"""The `ApproveClearance` command -- intent dataclass for this slice.

The approving actor's identity is captured via `principal_id` on the
envelope (`StoredEvent.principal_id`) per cross-BC `RunAborted` /
`ProcedureAborted` precedent. No `approving_actor_id` field on the
command or the event payload; the envelope is the single source of
truth for "who triggered this transition".

Optional `valid_from` / `valid_until` overrides defaults set at
register time. Approving carries the chance to set/refine the
validity window once the reviewer has finalised acceptance terms.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ApproveClearance:
    """Approve an UnderReview clearance (`UnderReview -> Approved`)."""

    clearance_id: UUID
    valid_from: datetime | None = None
    valid_until: datetime | None = None
