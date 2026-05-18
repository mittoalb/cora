"""The `ListFamilies` query: intent dataclass for keyset-paginated
list of capabilities from the projection.

Single optional filter: status (Defined / Versioned / Deprecated).
Family is flat (no hierarchy, no parent), so the shape is the
simpler sibling of `ListAssets`: status filter only, mirroring
`ListSubjects`. Cursor encodes (created_at, family_id).
"""

from dataclasses import dataclass
from typing import Literal

FamilyStatusFilter = Literal[
    "Defined",
    "Versioned",
    "Deprecated",
]


@dataclass(frozen=True)
class ListFamilies:
    """Read a keyset-paginated page of capabilities from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    status: FamilyStatusFilter | None = None
    """Optional status filter (one of the FamilyStatus values)."""
