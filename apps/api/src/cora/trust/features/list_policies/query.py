"""The `ListPolicies` query: intent dataclass for keyset-paginated
list of policies from the projection.

Single optional UUID filter: conduit_id (the Conduit each Policy
governs). Cursor encodes (created_at, policy_id).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListPolicies:
    """Read a keyset-paginated page of policies from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    conduit_id: UUID | None = None
    """Optional `conduit_id` filter: returns Policies governing the
    given Conduit. Pass `None` (omit) for "any Conduit"."""
