"""The `ListSubjects` query — intent dataclass for keyset-paginated
list of subjects from the projection.

Reads `proj_subject_summary`; never the event stream directly.
Status filter accepts every `SubjectStatus` enum value (PascalCase
per the BC-map vocabulary). Cursor encodes (created_at, subject_id).
"""

from dataclasses import dataclass
from typing import Literal

SubjectStatusFilter = Literal[
    "Received",
    "Mounted",
    "Measured",
    "Removed",
    "Returned",
    "Stored",
    "Discarded",
]


@dataclass(frozen=True)
class ListSubjects:
    """Read a keyset-paginated page of subjects from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    status: SubjectStatusFilter | None = None
    """Optional status filter. Omit to return all statuses."""
