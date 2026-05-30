"""The `ResumePermit` command: intent dataclass for this slice.

`permit_id` is the target Permit aggregate. The principal-id of the
invoker is supplied separately by the application handler at call
time; resume is operator-driven and carries no additional payload.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ResumePermit:
    """Operator resumes a Suspended Permit back to Active.

    Single-source: requires Permit to be in `Suspended` status. Strict-
    not-idempotent: resuming an already-Active (or any non-Suspended)
    permit raises `PermitCannotResumeError`.
    """

    permit_id: UUID
