"""Vertical slice for the `VersionMethod` command.

Module-as-namespace surface:

    from cora.recipe.features import version_method

    cmd = version_method.VersionMethod(method_id=..., version_tag="v2")
    handler = version_method.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.version_method import tool
from cora.recipe.features.version_method.command import VersionMethod
from cora.recipe.features.version_method.decider import decide
from cora.recipe.features.version_method.handler import Handler, bind
from cora.recipe.features.version_method.route import router

__all__ = [
    "Handler",
    "VersionMethod",
    "bind",
    "decide",
    "router",
    "tool",
]
