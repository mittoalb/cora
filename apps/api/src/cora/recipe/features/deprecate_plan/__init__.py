"""Vertical slice for the `DeprecatePlan` command.

Module-as-namespace surface:

    from cora.recipe.features import deprecate_plan

    cmd = deprecate_plan.DeprecatePlan(plan_id=...)
    handler = deprecate_plan.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.deprecate_plan import tool
from cora.recipe.features.deprecate_plan.command import DeprecatePlan
from cora.recipe.features.deprecate_plan.decider import decide
from cora.recipe.features.deprecate_plan.handler import Handler, bind
from cora.recipe.features.deprecate_plan.route import router

__all__ = [
    "DeprecatePlan",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
