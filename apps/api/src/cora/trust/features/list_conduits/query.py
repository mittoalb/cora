"""The `ListConduits` query: intent dataclass for keyset-paginated
list of conduits from the projection.

Two optional UUID filters: source_zone_id and target_zone_id.
Combine to ask "all conduits between Zone A and Zone B" (intersect)
or pass one at a time for the single-endpoint variants. Cursor
encodes (created_at, conduit_id).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListConduits:
    """Read a keyset-paginated page of conduits from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    source_zone_id: UUID | None = None
    """Optional `source_zone_id` filter: returns conduits whose
    source endpoint is the given Zone. Pass `None` (omit) for
    "any source"."""

    target_zone_id: UUID | None = None
    """Optional `target_zone_id` filter: returns conduits whose
    target endpoint is the given Zone. Pass `None` (omit) for
    "any target"."""
