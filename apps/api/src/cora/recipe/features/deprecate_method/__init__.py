"""Vertical slice for the `DeprecateMethod` command.

Module-as-namespace surface:

    from cora.recipe.features import deprecate_method

    cmd = deprecate_method.DeprecateMethod(method_id=...)
    handler = deprecate_method.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.deprecate_method import tool
from cora.recipe.features.deprecate_method.command import DeprecateMethod
from cora.recipe.features.deprecate_method.decider import decide
from cora.recipe.features.deprecate_method.handler import Handler, bind
from cora.recipe.features.deprecate_method.route import router

__all__ = [
    "DeprecateMethod",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
