"""Slice: deprecate an existing Recipe.

Vertical slice. Mirrors `deprecate_capability` shape; no
cross-aggregate fan-out (Recipe deprecation does not load the
referenced Capability).
"""

from cora.recipe.features.deprecate_recipe import tool
from cora.recipe.features.deprecate_recipe.command import DeprecateRecipe
from cora.recipe.features.deprecate_recipe.decider import decide
from cora.recipe.features.deprecate_recipe.handler import Handler, bind
from cora.recipe.features.deprecate_recipe.route import router

__all__ = [
    "DeprecateRecipe",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
