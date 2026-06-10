"""Vertical slices for the Safety BC.

Slices:

Clearance lifecycle (11a-b):
  - `register_clearance`              (genesis -> Defined; create-style)
  - `get_clearance`                  (read; fold-on-read)
  - `submit_clearance`               (Defined -> Submitted)
  - `start_clearance_review`         (Submitted -> UnderReview)
  - `append_clearance_review_step`   (UnderReview; appends review_steps tuple)
  - `approve_clearance`              (UnderReview -> Approved)
  - `reject_clearance`               (UnderReview -> Rejected)
  - `activate_clearance`             (Approved -> Active)
  - `expire_clearance`               (Active -> Expired)
  - `amend_clearance`                (Active -> Superseded; atomic child registration)
  - `list_clearances`                (read; cursor-paginated over the projection)

Clearance template (9A+):
  - `define_clearance_template`      (genesis -> Draft)
  - `get_clearance_template`         (read; fold-on-read)
  - `list_clearance_templates`       (read; cursor-paginated over the projection)
  - `activate_clearance_template`    (Draft -> Active; 9B)
  - `deprecate_clearance_template`   (Active -> Deprecated; 9C)
  - `withdraw_clearance_template`    ((any) -> Withdrawn; 9C)
"""

from cora.safety.features import (
    activate_clearance,
    activate_clearance_template,
    amend_clearance,
    append_clearance_review_step,
    approve_clearance,
    define_clearance_template,
    deprecate_clearance_template,
    expire_clearance,
    get_clearance,
    get_clearance_template,
    list_clearance_templates,
    list_clearances,
    register_clearance,
    reject_clearance,
    start_clearance_review,
    submit_clearance,
    version_clearance_template,
    withdraw_clearance_template,
)

__all__ = [
    "activate_clearance",
    "activate_clearance_template",
    "amend_clearance",
    "append_clearance_review_step",
    "approve_clearance",
    "define_clearance_template",
    "deprecate_clearance_template",
    "expire_clearance",
    "get_clearance",
    "get_clearance_template",
    "list_clearance_templates",
    "list_clearances",
    "register_clearance",
    "reject_clearance",
    "start_clearance_review",
    "submit_clearance",
    "version_clearance_template",
    "withdraw_clearance_template",
]
