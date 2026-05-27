"""The `VoidVisit` command -- intent dataclass.

Records "this Visit should never have existed" -- FHIR R5 entered-in-
error analog. Distinguished from cancel (real allocation, pre-work
cancel) and abort (real work stopped). Use cases: BSS double-sent a
registration, duplicate Visit, registration error. Reason mandatory.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VoidVisit:
    """Transition any non-terminal status -> Voided (+ reason)."""

    visit_id: UUID
    reason: str
