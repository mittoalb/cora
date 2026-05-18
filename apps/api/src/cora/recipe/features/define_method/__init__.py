"""Vertical slice for the `DefineMethod` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.recipe.features import define_method

    cmd = define_method.DefineMethod(name="...", needed_families=frozenset({...}))
    handler = define_method.bind(deps)
    method_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.define_method import tool
from cora.recipe.features.define_method.command import DefineMethod
from cora.recipe.features.define_method.decider import decide
from cora.recipe.features.define_method.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.recipe.features.define_method.route import router

__all__ = [
    "DefineMethod",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
