"""The `ListZones` query: intent dataclass for keyset-paginated
list of zones from the projection.

No filters today: Zone has no cross-aggregate refs, and the
lifecycle status column is deferred per the additive-state pattern.
Cursor encodes (created_at, zone_id).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ListZones:
    """Read a keyset-paginated page of zones from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""
