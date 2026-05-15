"""The `RejectClearance` command -- intent dataclass for this slice.

`reason` is operator-supplied free text captured on the emitted event
for audit clarity (e.g., "ESRB found insufficient PPE specification",
"chemical inventory exceeds beamline limit"). Mirrors RunAbortReason
1-500 char shape.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RejectClearance:
    """Reject an UnderReview clearance (`UnderReview -> Rejected`).

    `rejecting_actor_id` is filled by the route layer from the request's
    authenticated principal. The decider trusts this field; cross-BC
    Authorize gating happens at the handler-level pre-decide step.
    Folded into Clearance state as `last_reviewed_by_actor_id`.
    """

    clearance_id: UUID
    rejecting_actor_id: UUID
    reason: str
