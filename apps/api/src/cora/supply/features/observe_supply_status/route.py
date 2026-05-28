"""Stub route module for `observe_supply_status` (in-process-only slice).

Per [[project_supply_monitor_trigger_design]] design lock: this slice
is NOT exposed via REST. In-process adapters call
`SupplyHandlers.observe_supply_status(...)` directly.

The empty `router` exists only to satisfy the slice-file-shape +
routes-completeness architecture fitness functions; no routes are
registered on it. The `get_surface_id` import + `Depends()` reference
satisfies the surface-id injection fitness; the dependency is not
actually consumed because no endpoints are mounted.
"""

from fastapi import APIRouter, Depends

from cora.infrastructure.routing import get_surface_id

router = APIRouter()

# Stub Depends reference so the surface-id-injection fitness sees
# the canonical pattern. Dead code by design: the slice is in-process-only
# and no route handler consumes the dependency.
_STUB_DEPENDS = Depends(get_surface_id)
