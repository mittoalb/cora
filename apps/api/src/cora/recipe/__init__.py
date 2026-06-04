"""Recipe bounded context.

Owns the recipe-and-procedure concerns of CORA. Five aggregates per
[[project-recipe-aggregate-design]] (SHIPPED on main 2026-06-03 via
PR #24); the ladder mirrors ISA-88's Recipe type hierarchy (General -> Site ->
Master -> Control) with Capability as the operations-layer contract
that Methods and Recipes bind to:

  - `Capability` -- operations-layer contract. Declares
    `executor_shapes`, `parameters_schema`, and
    `required_affordances`. Templates that Methods and Recipes refer
    to by `capability_id` for the lifetime of the dependent.
  - `Method` ~= ISA-88 General Recipe -- the technique class, vendor
    / scientific-community level. Equipment-agnostic (refers to
    `Family` ids). `Method.parameters_schema` is a STRICT subset of
    the bound Capability's schema.
  - `Practice` ~= ISA-88 Site Recipe -- a facility's adapted version
    of a Method (institutional constraints, default parameter
    envelopes, safety overlay), still abstract over which Asset
    performs it.
  - `Plan` ~= ISA-88 Master / Control Recipe -- concrete binding of
    a Method (or Practice) to specific Asset instances + wiring,
    ready to schedule or execute. `define_plan` checks the
    family-superset invariant via the `PlanBindingContext` pattern.
  - `Recipe` -- the executable parameterized step sequence. Pins an
    immutable `capability_id`; carries templated steps with
    `BindingRef` sentinels; instantiated into a runtime Procedure
    via the Operation BC's `register_procedure_from_recipe`.

`Run` (the actual execution) lives in the Run BC, not here, but
binds back to Plan + Subject.

## Versioning-contract divergence

Two versioning semantics span the ladder (intentional, load-bearing,
see [[project-recipe-aggregate-design]]):

  - **Capability is REPLACE-WHOLESALE.** `version_capability` accepts
    the full declarative contract (`executor_shapes`,
    `parameters_schema`, `description`) on every call; each
    `CapabilityVersioned` event carries a complete new contract.
    Bindings point at the Capability aggregate, not at a specific
    version-tag; re-versioning replaces the contract in-place.
  - **Method / Plan / Practice / Recipe are INCREMENTAL-LABEL.**
    `version_*` slices accept a new `version_tag` plus the
    delta-bearing fields (Plan: `wires` + `default_parameters`;
    Recipe: `steps`; Method: `parameters_schema` +
    `needed_family_ids`; Practice: parameter overrides). Each
    version is content-addressed; the upstream binding
    (`capability_id`, `method_id`, `practice_id`) stays IMMUTABLE
    across versions of the binding aggregate.

The asymmetry is deliberate: Capability is a contract whose identity
is its name + lineage; Method / Plan / Practice / Recipe each carry
an evolving body whose changes operators want to track by labeled
version. Operator-facing wire shapes follow suit: Capability's
version events redeclare the contract; the rest carry deltas.

## Genesis-event convention

All five aggregates emit `<X>Defined` at registration per
[[project-defined-vs-registered-genesis]]: each is a template /
contract / blueprint. Distinct from the Operation BC's
`ProcedureRegistered` (records that a runtime Procedure instance
exists, possibly bound to a Recipe via the recipe-replay path).

Track-A BC: depends on `Equipment.Family` (referenced by
`Method.needed_family_ids`) and `Equipment.Asset` (referenced by
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
