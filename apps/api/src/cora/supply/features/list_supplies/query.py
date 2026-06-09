"""The `ListSupplies` query: intent dataclass for keyset-paginated
list of supplies from the projection.

Four optional filters: facility_code (cross-deployment convergent
slug; exact match), containing_asset_id (UUID of the physical-
equipment containment back-reference; exact match), kind (free-form
bare-str discriminator; exact match), status (one of the six
SupplyStatus values, including the lifecycle-terminal
`Decommissioned`). All four correspond to real ops queries:
"all LN2 supplies" (kind), "all supplies bound to 2-BM" (containing
asset), "all supplies owned by APS" (facility code), "all
unavailable supplies" (status).

The prior `?scope=` filter was retired in favor of the structural
`?facility_code=` + `?containing_asset_id=` filters per
[[project_supply_sector_disposition]] Option A; the SupplyScope
retirement cleanup then dropped the decorative `scope` column from
the projection and the response DTO entirely. The structural address
is the canonical shape going forward.

No default exclusion of Decommissioned rows: matches the cross-BC
convention from Asset (`AssetLifecycleFilter` includes
`Decommissioned`) and Subject (`SubjectStatusFilter` includes
`Discarded`). An unfiltered `list_supplies` returns every status;
callers who want only-active set `status=...` explicitly. Callers
who want to audit decommissioned supplies set `status=Decommissioned`.

`SupplyStatusFilter` is locked at the full enum width: forward-compat
motivation: when later transition slices land, no Pydantic schema
change required; OpenAPI documents the full FSM up front for ops
engineers. Same precedent as TriggerSource being locked 3-value day
one.

Cursor encodes (registered_at, supply_id): `registered_at` is set
once at SupplyRegistered (immutable), so it's a stable keyset key.
Mirrors `list_families` cursor exactly.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

SupplyStatusFilter = Literal[
    "Unknown",
    "Available",
    "Degraded",
    "Unavailable",
    "Recovering",
    "Decommissioned",
]


@dataclass(frozen=True)
class ListSupplies:
    """Read a keyset-paginated page of supplies from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    facility_code: str | None = None
    """Optional facility-code filter (exact match against the cross-
    deployment convergent slug, for example `'aps'`, `'maxiv'`)."""

    containing_asset_id: UUID | None = None
    """Optional containing-Asset-id filter (exact match against the
    Equipment BC Asset id; non-NULL projection rows only). Omit to
    return both facility-scope and contained Supplies."""

    kind: str | None = None
    """Optional kind filter (free-form, exact match)."""

    status: SupplyStatusFilter | None = None
    """Optional status filter (one of the six SupplyStatus values)."""
