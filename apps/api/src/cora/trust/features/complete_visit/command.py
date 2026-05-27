"""The `CompleteVisit` command -- intent dataclass.

Normal terminal: visit's work is done, allocation closes cleanly.
Distinct from cancel (pre-work, never started), abort (mid-work but
stopped abnormally), and void (registration error). No reason on
Complete -- it's the happy path.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CompleteVisit:
    """Transition InProgress | OnHold -> Completed."""

    visit_id: UUID
