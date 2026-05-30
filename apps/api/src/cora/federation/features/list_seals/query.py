"""The `ListSeals` query: intent dataclass for the read slice.

Cursor pagination + optional `status` filter. Each filter is optional;
passing None means "do not filter on this dimension". `limit` defaults
to 50 (capped at 100 in the route layer per the 8e-1c convention).

`cursor` is opaque base64-encoded `(initialized_at, seal_stream_uuid)`
where the cursor UUID is the deterministic UUID5 derivation of
`facility_id` via `seal_stream_id` (the projection's PK is text
`facility_id`; the factory contract requires a UUID cursor id, so the
slice's `item_cursor_id` lambda derives one from the row's
facility_id).

Filter set is intentionally tiny: Seal is a singleton per facility, so
a list-all returns at most `len(facilities)` rows. Add filters only
when a real consumer asks.
"""

from dataclasses import dataclass
from typing import Literal

SealStatusFilter = Literal["Live", "Republishing"]


@dataclass(frozen=True)
class ListSeals:
    """List Seals (one per facility) with cursor pagination + status filter."""

    cursor: str | None = None
    limit: int = 50
    status: SealStatusFilter | None = None
