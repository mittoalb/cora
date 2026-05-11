"""Recipe bounded context.

Owns the recipe-and-procedure concerns of CORA. Per the BC map, the
recipe ladder is a 4-level structure that mirrors ISA-88's Recipe
type hierarchy (General → Site → Master → Control):

  - `Method` ≈ ISA-88 General Recipe — the technique class, vendor /
    scientific-community level. Equipment-agnostic (refers to
    `Capability` ids, not specific Asset instances). Phase 6a.
  - `Practice` ≈ ISA-88 Site Recipe — a facility's adapted version
    of a Method (institutional constraints, default parameter
    envelopes, safety overlay), still abstract over which Asset
    performs it. Phase 6d.
  - `Plan` ≈ ISA-88 Master / Control Recipe — concrete binding of a
    Method (or Practice) to a specific Asset instance, ready to
    schedule or execute. Phase 6e.
  - `Run` — the actual execution. High-cardinality streams; first
    BC where substreams territory becomes relevant. Phase 6f.

Track-A BC: depends on `Equipment.Capability` (referenced by
`Method.needs_capabilities`) and (later) `Equipment.Asset`
(referenced by `Plan` binding). Cross-aggregate refs use the
eventual-consistency stance (decider does NOT verify referenced
Capability / Asset exists; precedent locked at Trust 3b).

Phase history (✅ all shipped except 6c, 6f):
  - 6a: `Method` + `define_method` + `get_method`
  - 6b: Method transitions (version, deprecate)
  - 6d: Practice aggregate (define + get + version + deprecate)
  - 5f: Asset.capabilities (just-in-time before Plan; Equipment side)
  - 6e: Plan aggregate (define + get + version + deprecate; binds
    Practice + multi-asset set with capability-superset check via
    PlanBindingContext pattern)
  - 6c (deferred): Method/Practice/Plan enrichment (description,
    owner, default parameters) — defer-candidate
  - 6f: Run aggregate (the keystone; binds Plan + Subject)

Layout (mirrors Equipment / Trust / Subject):
    aggregates/<aggregate>/   -- aggregate state, events union, evolver, read
    features/<verb>_<noun>/   -- vertical slice: command/query + decider? + handler + route + tool
    wire.py                   -- RecipeHandlers bundle + wire_recipe(deps)
    routes.py                 -- register_recipe_routes(app)
    tools.py                  -- register_recipe_tools(mcp, *, get_handlers)
"""

from cora.recipe.errors import UnauthorizedError
from cora.recipe.routes import register_recipe_routes
from cora.recipe.tools import register_recipe_tools
from cora.recipe.wire import RecipeHandlers, wire_recipe

__all__ = [
    "RecipeHandlers",
    "UnauthorizedError",
    "register_recipe_routes",
    "register_recipe_tools",
    "wire_recipe",
]
