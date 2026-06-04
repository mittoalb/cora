"""Equipment bounded context.

Owns the equipment-and-family concerns of CORA:
  - `Family` (technique-class catalog; what an equipment type
    can do, equipment-agnostic, cross-facility). Referenced by
    `Recipe.Method.needed_family_ids` to express a Method's
    hardware contract.
  - `Asset` (physical equipment instance; hierarchical, lifecycle-
    managed). Referenced by `Recipe.Plan` and `Operation.Procedure`.

Foundation-tier BC: every Track A and Track B BC depends on
Family and/or Asset. Built before Recipe so Method's
`needed_family_ids` resolves to real Family ids instead of
bare UUIDs (the eventual-consistency fallback that Trust uses for
Conduit's zone refs).

## Asset.level posture (ISA-88-derived, conventional not enforced)

`Asset.level` follows the ISA-88 hierarchy (Enterprise / Site / Area
/ Unit / Component / Device) as a single-word StrEnum. The
single-parent tree rule (`parent_id` chain, no cycles) IS structurally
enforced; the level ordering is NOT. CORA permits Device-in-Device
parent chains when the parent is an addressable control surface
(smart instruments, networked subassemblies). Operator guidance:
default to strict ordering; reach for nesting only when the physical
hardware genuinely composes that way (per [[project-bc-map]] +
glossary). The state.py docstring carries the canonical phrasing;
this BC docstring surfaces the posture so operators reading the BC
introduction find it without spelunking into the aggregate file.

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
