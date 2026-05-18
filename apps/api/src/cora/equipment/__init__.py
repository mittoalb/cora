"""Equipment bounded context.

Owns the equipment-and-capability concerns of CORA:
  - `Family` (technique-class catalog; what an equipment type
    can do, equipment-agnostic, cross-facility). Referenced by
    `Recipe.Method.needs.capabilities` to express a Method's
    hardware contract.
  - `Asset` (physical equipment instance; hierarchical, lifecycle-
    managed). Referenced by `Recipe.Plan` and `Operation.Procedure`.
    Lands in 5b+; not in 5a.

Foundation-tier BC: every Track A and Track B BC depends on
Family and/or Asset. Built before Recipe so Method's
`needs.capabilities` resolves to real Family ids instead of
bare UUIDs (the eventual-consistency fallback that Trust uses for
Conduit's zone refs).

Phase 5a ships `Family` + `define_family` + `get_family`.
Subsequent phases:
  - 5b: Asset aggregate scaffold + register_asset
  - 5c: Asset lifecycle (activate, decommission)
  - 5d: Asset hierarchy (relocate)
  - 5e: get_asset + maintenance lifecycle
  - 5f+: Family transitions, Asset condition/settings/ports/
    owner/PIDINST

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver, read
    features/<verb>_<noun>/   -- vertical slice: command/query + decider? + handler + route + tool
    wire.py                   -- EquipmentHandlers bundle + wire_equipment(deps)
    routes.py                 -- register_equipment_routes(app)
"""

from cora.equipment._projections import register_equipment_projections
from cora.equipment.errors import UnauthorizedError
from cora.equipment.routes import register_equipment_routes
from cora.equipment.tools import register_equipment_tools
from cora.equipment.wire import EquipmentHandlers, wire_equipment

__all__ = [
    "EquipmentHandlers",
    "UnauthorizedError",
    "register_equipment_projections",
    "register_equipment_routes",
    "register_equipment_tools",
    "wire_equipment",
]
