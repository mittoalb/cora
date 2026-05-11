"""Vertical slice for the `DeprecatePractice` command.

Module-as-namespace surface:

    from cora.recipe.features import deprecate_practice

    cmd = deprecate_practice.DeprecatePractice(practice_id=...)
    handler = deprecate_practice.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.deprecate_practice import tool
from cora.recipe.features.deprecate_practice.command import DeprecatePractice
from cora.recipe.features.deprecate_practice.decider import decide
from cora.recipe.features.deprecate_practice.handler import Handler, bind
from cora.recipe.features.deprecate_practice.route import router

__all__ = [
    "DeprecatePractice",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
