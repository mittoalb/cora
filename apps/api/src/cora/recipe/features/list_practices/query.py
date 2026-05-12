"""The `ListPractices` query: intent dataclass for keyset-paginated
list of practices from the projection.

Two optional filters: status (Defined / Versioned / Deprecated) and
method_id (which Method this Practice implements). Combine for
queries like "show me all Versioned Practices implementing
Method X". Cursor encodes (created_at, practice_id).
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

PracticeStatusFilter = Literal[
    "Defined",
    "Versioned",
    "Deprecated",
]


@dataclass(frozen=True)
class ListPractices:
    """Read a keyset-paginated page of practices from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    status: PracticeStatusFilter | None = None
    """Optional status filter (one of the PracticeStatus values)."""

    method_id: UUID | None = None
    """Optional `method_id` filter: returns Practices implementing
    the given Method. Pass `None` (omit) for "any Method"."""
