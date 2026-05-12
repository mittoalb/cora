"""The `ListPlans` query: intent dataclass for keyset-paginated
list of plans from the projection.

Two optional filters: status (Defined / Versioned / Deprecated) and
practice_id (which Practice this Plan binds). Combine for queries
like "show me all Versioned Plans for Practice X". Cursor encodes
(created_at, plan_id).
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

PlanStatusFilter = Literal[
    "Defined",
    "Versioned",
    "Deprecated",
]


@dataclass(frozen=True)
class ListPlans:
    """Read a keyset-paginated page of plans from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    status: PlanStatusFilter | None = None
    """Optional status filter (one of the PlanStatus values)."""

    practice_id: UUID | None = None
    """Optional `practice_id` filter: returns Plans binding the given
    Practice. Pass `None` (omit) for "any Practice"."""
