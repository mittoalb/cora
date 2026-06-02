"""Slice: issue a new version label + replacement steps for an existing Recipe.

Vertical slice. Mirrors `version_capability` plus a cross-aggregate
BindingRef re-validation against the CURRENT Capability state at
write time (per anti-hook 5 of
[[project-recipe-aggregate-design]]: the same validator that fires
at define_recipe time fires again here, closing the operator-side
half of the Capability-re-version race).
"""

from cora.recipe.features.version_recipe import tool
from cora.recipe.features.version_recipe.command import VersionRecipe
from cora.recipe.features.version_recipe.decider import decide
from cora.recipe.features.version_recipe.handler import Handler, bind
from cora.recipe.features.version_recipe.route import router

__all__ = [
    "Handler",
    "VersionRecipe",
    "bind",
    "decide",
    "router",
    "tool",
]
