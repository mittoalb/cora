"""The `SubmitClearance` command -- intent dataclass for this slice.

`clearance_id` is the target. No body fields: submitting is the
operator's gesture moving a Defined clearance to Submitted (awaiting
first reviewer pickup).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SubmitClearance:
    """Submit a Defined clearance for review (`Defined -> Submitted`)."""

    clearance_id: UUID
