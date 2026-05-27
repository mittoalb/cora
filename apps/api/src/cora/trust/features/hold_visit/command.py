"""The `HoldVisit` command -- intent dataclass.

Pauses an InProgress Visit. OnHold is reserved for genuine envelope
pauses: beam dump, equipment fault, safety hold, extended user break.
Per design memo lock, NOT used for nested-child commissioning -- in
that case parent stays InProgress and the control concern lives on
`proj_surface_active_visit`.

`reason` is mandatory (1-500 chars). Reason fields MUST NOT contain
PII per [[project_visit_aggregate_design]] lock; UI placeholder warns.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class HoldVisit:
    """Transition InProgress -> OnHold (+ reason)."""

    visit_id: UUID
    reason: str
