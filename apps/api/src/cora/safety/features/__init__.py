"""Vertical slices for the Safety BC.

Phase 11a-a ships:
  - `register_clearance` (genesis -> Defined; create-style)
  - `get_clearance`      (read; fold-on-read)

Phase 11a-b adds the FSM-closure transitions:
  - `submit_clearance`               (Defined -> Submitted)
  - `start_review_clearance`         (Submitted -> UnderReview)
  - `append_clearance_review_step`   (UnderReview; appends review_steps tuple)
  - `approve_clearance`              (UnderReview -> Approved)
  - `reject_clearance`               (UnderReview -> Rejected)
  - `activate_clearance`             (Approved -> Active)
  - `list_clearances`                (read; cursor-paginated over the projection)

Phase 11a-c adds:
  - `expire_clearance`               (Active -> Expired)
  - `amend_clearance`                (Active -> Superseded; atomic child registration)
"""

from cora.safety.features import (
    activate_clearance,
    append_clearance_review_step,
    approve_clearance,
    get_clearance,
    list_clearances,
    register_clearance,
    reject_clearance,
    start_review_clearance,
    submit_clearance,
)

__all__ = [
    "activate_clearance",
    "append_clearance_review_step",
    "approve_clearance",
    "get_clearance",
    "list_clearances",
    "register_clearance",
    "reject_clearance",
    "start_review_clearance",
    "submit_clearance",
]
