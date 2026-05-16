"""The `RejectClearance` command -- intent dataclass for this slice.

`reason` is operator-supplied free text captured on the emitted event
for audit clarity (e.g., "ESRB found insufficient PPE specification",
"chemical inventory exceeds beamline limit"). Mirrors RunAbortReason
1-500 char shape.

The rejecting actor's identity lives on the event envelope
(`StoredEvent.principal_id`), not on the command/event payload. The
projection reads the envelope at apply time. No `rejecting_actor_id`
field on the command, per cross-BC `RunAborted` / `ProcedureAborted`
precedent.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RejectClearance:
    """Reject an UnderReview clearance (`UnderReview -> Rejected`)."""

    clearance_id: UUID
    reason: str
