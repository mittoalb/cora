"""Slice: define a new Recipe against an existing Capability.

Vertical slice. Mirrors `define_capability` and `define_method` in
shape and discipline; adds a cross-aggregate fan-out at handler time
to load the referenced Capability and validate BindingRef integrity
against its `parameters_schema`.
"""

from cora.recipe.features.define_recipe import tool
from cora.recipe.features.define_recipe.command import DefineRecipe
from cora.recipe.features.define_recipe.decider import decide
from cora.recipe.features.define_recipe.handler import Handler, IdempotentHandler, bind
from cora.recipe.features.define_recipe.route import router

__all__ = [
    "DefineRecipe",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
