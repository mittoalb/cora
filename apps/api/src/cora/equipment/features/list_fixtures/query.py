"""The `ListFixtures` query: intent dataclass for keyset-paginated
list of Fixtures from the projection.

Three optional, combinable filters: `assembly_id`, `surface_id`,
`assembly_content_hash`. Each filter is backed by an index from the
B.4 fixture-summary migration:
  - assembly_id          -> surface_assembly composite index
  - surface_id           -> surface_assembly composite index
  - assembly_content_hash -> content_hash index (federation queries)

Cursor encodes (created_at, fixture_id), DESC most-recent-first.
Per-row scoping deferred until ReBAC (command-name gating only).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListFixtures:
    """Read a keyset-paginated page of Fixtures from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    assembly_id: UUID | None = None
    """Optional filter: only Fixtures of this Assembly blueprint."""

    surface_id: UUID | None = None
    """Optional filter: only Fixtures registered on this Trust Surface."""

    assembly_content_hash: str | None = None
    """Optional filter: only Fixtures whose snapshot matches this
    content_hash. Useful for cross-Surface federation queries
    ('find every realization of blueprint X across facilities')."""
