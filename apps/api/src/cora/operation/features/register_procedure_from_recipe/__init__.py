"""Slice: register a new Procedure by expanding a Recipe's templated steps.

Vertical slice. Mirrors `register_procedure` shape (create-style,
idempotency-wrappable) plus a cross-aggregate Recipe + Capability
fan-out: the handler loads the Recipe, then the Recipe's Capability,
then re-validates BindingRef integrity against the CURRENT Capability
schema (raises `RecipeBindingsStaleAgainstCurrentCapabilityError` on
drift), validates operator-supplied `bindings` against
`Capability.parameters_schema`, runs the expansion port twice for
overflow + determinism gates, and emits a 2-event genesis block:
`ProcedureRegistered` (with `recipe_id` + denorm `capability_id` set)
plus `RecipeExpansionRecorded` (template-invocation-grain provenance).

Per anti-hook 18 of [[project-recipe-aggregate-design]]: missing
Capability re-uses the existing `CapabilityNotFoundError` from Recipe
BC, no new error class invented.
"""

from cora.operation.features.register_procedure_from_recipe import tool
from cora.operation.features.register_procedure_from_recipe.command import (
    RegisterProcedureFromRecipe,
)
from cora.operation.features.register_procedure_from_recipe.decider import decide
from cora.operation.features.register_procedure_from_recipe.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.operation.features.register_procedure_from_recipe.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterProcedureFromRecipe",
    "bind",
    "decide",
    "router",
    "tool",
]
