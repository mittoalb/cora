"""The `ListSupplies` query: intent dataclass for keyset-paginated
list of supplies from the projection.

Three optional filters: scope (Facility / Sector / Beamline), kind
(free-form bare-str discriminator, exact match), status (one of the
five SupplyStatus values). All three correspond to real ops queries:
"all LN2 supplies" (kind), "all beamline-scope supplies" (scope),
"all unavailable supplies" (status).

`SupplyStatusFilter` and `SupplyScopeFilter` are locked at the full
enum width day one, even though only `Unknown` and `Available` are
reachable from the initial slices (the other 3 statuses become
reachable when the later transition slices ship). The forward-compat
motivation: when those land, no Pydantic schema change required;
OpenAPI documents the full FSM up front for ops engineers. Same
precedent as TriggerSource being locked 3-value day one.

Cursor encodes (registered_at, supply_id) — `registered_at` is set
once at SupplyRegistered (immutable), so it's a stable keyset key.
Mirrors `list_families` cursor exactly.
"""

from dataclasses import dataclass
from typing import Literal

SupplyScopeFilter = Literal[
    "Facility",
    "Sector",
    "Beamline",
]

SupplyStatusFilter = Literal[
    "Unknown",
    "Available",
    "Degraded",
    "Unavailable",
    "Recovering",
]


@dataclass(frozen=True)
class ListSupplies:
    """Read a keyset-paginated page of supplies from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    scope: SupplyScopeFilter | None = None
    """Optional scope filter (one of the SupplyScope values)."""

    kind: str | None = None
    """Optional kind filter (free-form, exact match)."""

    status: SupplyStatusFilter | None = None
    """Optional status filter (one of the five SupplyStatus values)."""
