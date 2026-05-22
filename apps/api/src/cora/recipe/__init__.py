"""Recipe bounded context.

Owns the recipe-and-procedure concerns of CORA. Per the BC map, the
recipe ladder is a 4-level structure that mirrors ISA-88's Recipe
type hierarchy (General → Site → Master → Control):

  - `Method` ≈ ISA-88 General Recipe — the technique class, vendor /
    scientific-community level. Equipment-agnostic (refers to
    `Family` ids, not specific Asset instances).
  - `Practice` ≈ ISA-88 Site Recipe — a facility's adapted version
    of a Method (institutional constraints, default parameter
    envelopes, safety overlay), still abstract over which Asset
    performs it.
  - `Plan` ≈ ISA-88 Master / Control Recipe — concrete binding of a
    Method (or Practice) to a specific Asset instance, ready to
    schedule or execute. Binds Practice + multi-asset set with
    family-superset check via the `PlanBindingContext` pattern.
  - `Capability` — universal template that Methods (and
    Operation.Procedures) realize as executor-shaped variants.
  - `Run` — the actual execution. Lives in the Run BC, not here,
    but binds back to Plan + Subject.

Track-A BC: depends on `Equipment.Family` (referenced by
`Method.needed_families`) and `Equipment.Asset` (referenced by
`Plan` binding). Cross-aggregate refs use the eventual-consistency
stance: the decider does NOT verify the referenced Family / Asset
exists; the precedent comes from Trust BC's Conduit zone refs.

Layout (mirrors Equipment / Trust / Subject):
    aggregates/<aggregate>/   -- aggregate state, events union, evolver, read
    features/<verb>_<noun>/   -- vertical slice: command/query + decider? + handler + route + tool
    wire.py                   -- RecipeHandlers bundle + wire_recipe(deps)
    routes.py                 -- register_recipe_routes(app)
    tools.py                  -- register_recipe_tools(mcp, *, get_handlers)
"""

from cora.recipe._projections import register_recipe_projections
from cora.recipe.errors import UnauthorizedError
from cora.recipe.routes import register_recipe_routes
from cora.recipe.tools import register_recipe_tools
from cora.recipe.wire import RecipeHandlers, wire_recipe

__all__ = [
    "RecipeHandlers",
    "UnauthorizedError",
    "register_recipe_projections",
    "register_recipe_routes",
    "register_recipe_tools",
    "wire_recipe",
]
