"""The `StartVisit` command -- intent dataclass.

Explicit operator gesture: work is beginning. Distinct from
take_control_of_surface -- a Visit can be InProgress without holding
any Surface.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StartVisit:
    """Transition Arrived -> InProgress."""

    visit_id: UUID
