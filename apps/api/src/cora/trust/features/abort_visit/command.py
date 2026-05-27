"""The `AbortVisit` command -- intent dataclass.

Aborts a Visit AFTER work began. Distinct from cancel (pre-work) and
void (registration error). HL7 v2 A13 precedent (cancel-discharge,
distinct from A11 cancel-admit). Reason mandatory.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AbortVisit:
    """Transition InProgress | OnHold -> Aborted (+ reason)."""

    visit_id: UUID
    reason: str
