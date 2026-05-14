"""Vertical slice for the `UpdateMethodParametersSchema` command."""

from cora.recipe.features.update_method_parameters_schema import tool
from cora.recipe.features.update_method_parameters_schema.command import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_method_parameters_schema.decider import decide
from cora.recipe.features.update_method_parameters_schema.handler import Handler, bind
from cora.recipe.features.update_method_parameters_schema.route import router

__all__ = [
    "Handler",
    "UpdateMethodParametersSchema",
    "bind",
    "decide",
    "router",
    "tool",
]
