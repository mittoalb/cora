"""Vertical slice for the `VersionPlan` command.

Module-as-namespace surface:

    from cora.recipe.features import version_plan

    cmd = version_plan.VersionPlan(plan_id=..., version_tag="v2")
    handler = version_plan.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.version_plan import tool
from cora.recipe.features.version_plan.command import VersionPlan
from cora.recipe.features.version_plan.decider import decide
from cora.recipe.features.version_plan.handler import Handler, bind
from cora.recipe.features.version_plan.route import router

__all__ = [
    "Handler",
    "VersionPlan",
    "bind",
    "decide",
    "router",
    "tool",
]
