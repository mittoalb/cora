"""The `ListProcedures` query: intent dataclass for keyset-paginated
list of procedures from the projection.

Four optional filters: status (one of the 5 ProcedureStatus values),
kind (free-form bare-str discriminator, exact match), parent_run_id
(UUID for Phase-of-Run filtering), target_asset_id (UUID for
"procedures targeting this Asset" via the GIN index on the
target_asset_ids UUID[] column).

`ProcedureStatusFilter` is locked at the full enum width day one
(Defined / Running / Completed / Aborted / Truncated). Same forward-
compat motivation as ListSupplies's SupplyStatusFilter.

Cursor encodes (registered_at, procedure_id) -- `registered_at` is
set once at ProcedureRegistered (immutable), so it's a stable keyset
key. Mirrors `list_supplies` cursor exactly.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ProcedureStatusFilter = Literal[
    "Defined",
    "Running",
    "Completed",
    "Aborted",
    "Truncated",
]


@dataclass(frozen=True)
class ListProcedures:
    """Read a keyset-paginated page of procedures from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    status: ProcedureStatusFilter | None = None
    """Optional status filter (one of the five ProcedureStatus values)."""

    kind: str | None = None
    """Optional kind filter (free-form, exact match; e.g. 'bakeout')."""

    parent_run_id: UUID | None = None
    """Optional Phase-of-Run filter; matches Procedures whose
    parent_run_id equals this UUID. None = match Procedures with ANY
    parent_run_id (including null); use the dedicated 'standalone'
    filter when that distinction matters (deferred until pilot need)."""

    target_asset_id: UUID | None = None
    """Optional target-Asset filter; matches Procedures whose
    target_asset_ids array contains this UUID (uses the GIN index on
    target_asset_ids for `WHERE $1 = ANY(target_asset_ids)`)."""
