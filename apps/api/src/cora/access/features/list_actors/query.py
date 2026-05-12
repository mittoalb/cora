"""The `ListActors` query — intent dataclass for keyset-paginated
list of actors.

Reads the `proj_access_actor_summary` projection table; never touches
the event stream directly. Filters are SQL-pushdown (status); cursor
encodes the (created_at, actor_id) of the last item the previous page
returned per Phase-8e D9 convention.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ListActors:
    """Read a keyset-paginated page of actors from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`.
    None on the first page; decodes via `cora.infrastructure.projection.
    decode_cursor` to `(created_at, actor_id)`."""

    limit: int = 50
    """Page size cap. Default 50 (modern REST band: Stripe / GitHub /
    Speakeasy guidance is 25-50 default, 100 max). Route-layer Pydantic
    Field enforces 1 <= limit <= 100."""

    status: Literal["active", "deactivated"] | None = None
    """Optional status filter. Omitting (None) returns all rows; explicit
    `status=active` or `status=deactivated` narrows. No magic 'all' value
    — implicit-omit is the modern convention (Speakeasy / Moesif)."""
