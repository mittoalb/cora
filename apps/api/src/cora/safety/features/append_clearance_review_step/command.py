"""The `AppendClearanceReviewStep` command -- intent dataclass for this slice.

Appends ONE step to the Clearance's `review_steps` tuple. Status stays
UnderReview; the chain grows by one. The terminal Approved/Rejected
transitions land via the dedicated `approve_clearance` /
`reject_clearance` slices once the chain is complete.

`actor_id` is filled by the route layer from the request's
authenticated principal (the actor who is RECORDING this step IS
the reviewer for this step). `decided_at` is operator-supplied (the
reviewer captures when they made the decision; may differ from
`occurred_at` which is when the slice was called).

`step_index` is enforced equal to `len(state.review_steps)` at the
decider per the append-only contract; out-of-order writes are
rejected.

`decision` is one of `Approved | Rejected | RequestedChanges` per the
design memo. `RequestedChanges` is a non-terminal step (the chain
continues; the operator addresses the changes and the next reviewer
records their step).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AppendClearanceReviewStep:
    """Append one reviewer step to an UnderReview clearance's chain."""

    clearance_id: UUID
    step_index: int
    role: str
    actor_id: UUID
    decision: str
    decided_at: datetime
    notes: str | None = None
