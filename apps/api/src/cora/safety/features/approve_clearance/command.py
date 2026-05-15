"""The `ApproveClearance` command -- intent dataclass for this slice.

`approving_actor_id` is filled by the route layer from the request's
authenticated principal. Folded into Clearance state as
`last_reviewed_by_actor_id`.

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
    approving_actor_id: UUID
    valid_from: datetime | None = None
    valid_until: datetime | None = None
