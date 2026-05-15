"""Supply bounded context.

Owns continuously-available resource state in CORA:

  - `Supply` aggregate (10a-a): a continuously-available resource
    that other aggregates depend on. Multiple instances at runtime,
    one per resource: photon beam, LN2, compressed air, electrical
    power, cooling water, vacuum, process gases, compute pool,
    FEL pulses, neutrons. Per the BC map: physical infrastructure
    delivering the resource (gas cabinets, compressors, mass-flow
    controllers) stays as `Asset`s; the resource itself is `Supply`.

Track B intro BC. Independent of Track A (Recipe / Subject / Data) and
of Trust / Decision foundation BCs. Method.needs.supplies wire-up
ships in 10b; physical-equipment binding (Supply -> Asset, mirrors
4f Subject -> Asset) is deferred-with-trigger to a later sub-phase.

Phase 10a-a ships the BC scaffold + `register_supply` (genesis ->
Unknown) + `mark_supply_available` (Unknown -> Available, operator
first observation) + `get_supply` + `list_supplies` + projection.

Phase 10a-b adds the full degradation/recovery cycle: `degrade_supply`
+ `mark_supply_unavailable` + `mark_supply_recovering` +
`restore_supply`.

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver, read
    features/<verb>_<noun>/   -- vertical slice: command/query + decider? + handler + route + tool
    projections/<aggregate>.py -- read-side projection consumed by list_*
    wire.py                   -- SupplyHandlers bundle + wire_supply(deps)
    routes.py                 -- register_supply_routes(app)
    tools.py                  -- register_supply_tools(mcp)

Phase 10a-a leaves `wire.py` / `routes.py` / `tools.py` /
`_projections.py` to land in iter 4 alongside the slice files.
"""
