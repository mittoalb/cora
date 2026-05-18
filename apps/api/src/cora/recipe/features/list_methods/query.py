"""The `ListMethods` query: intent dataclass for keyset-paginated
list of methods from the projection.

Single optional filter: status (Defined / Versioned / Deprecated),
mirroring `ListFamilies`. Method is the technique-class
definition, equipment-agnostic. Cursor encodes (created_at,
method_id).
"""

from dataclasses import dataclass
from typing import Literal

MethodStatusFilter = Literal[
    "Defined",
    "Versioned",
    "Deprecated",
]


@dataclass(frozen=True)
class ListMethods:
    """Read a keyset-paginated page of methods from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    status: MethodStatusFilter | None = None
    """Optional status filter (one of the MethodStatus values)."""
