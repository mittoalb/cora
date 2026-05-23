"""Supply BC projections.

Single-aggregate BC, single projection: SupplySummaryProjection
backs `GET /supplies` (list) and complements `GET /supplies/{id}`
(which still uses fold-on-read for canonical state).

Add a new projection by creating a new module here + re-exporting
its class + adding it to `register_supply_projections`.
"""

from cora.supply.projections.supply import SupplySummaryProjection

__all__ = ["SupplySummaryProjection"]
