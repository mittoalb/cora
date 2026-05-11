"""Vertical slice for the `DefinePlan` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.recipe.features import define_plan

    cmd = define_plan.DefinePlan(name="...", practice_id=..., asset_ids={...})
    handler = define_plan.bind(deps)
    plan_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.define_plan import tool
from cora.recipe.features.define_plan.command import DefinePlan
from cora.recipe.features.define_plan.context import PlanBindingContext
from cora.recipe.features.define_plan.decider import decide
from cora.recipe.features.define_plan.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.recipe.features.define_plan.route import router

__all__ = [
    "DefinePlan",
    "Handler",
    "IdempotentHandler",
    "PlanBindingContext",
    "bind",
    "decide",
    "router",
    "tool",
]
