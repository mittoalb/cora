"""The `CancelVisit` command -- intent dataclass.

Cancels a Visit BEFORE work began. Distinct from abort (mid-work) and
void (registration error). HL7 v2 A11 precedent (cancel-admit vs A13
cancel-discharge). Reason mandatory.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CancelVisit:
    """Transition Planned | Arrived -> Cancelled (+ reason)."""

    visit_id: UUID
    reason: str
