"""Slice: read the current state of a Recipe by id.

Vertical slice. Mirrors `get_capability` shape (Path C:
projection-sourced lifecycle timestamps merged with aggregate state).
"""

from cora.recipe.features.get_recipe import tool
from cora.recipe.features.get_recipe.handler import Handler, RecipeView, bind
from cora.recipe.features.get_recipe.query import GetRecipe
from cora.recipe.features.get_recipe.route import router

__all__ = ["GetRecipe", "Handler", "RecipeView", "bind", "router", "tool"]
