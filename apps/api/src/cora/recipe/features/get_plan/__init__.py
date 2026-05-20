"""Vertical slice for the `GetPlan` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.recipe.features import get_plan

    q = get_plan.GetPlan(plan_id=...)
    handler = get_plan.bind(deps)
    plan = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.get_plan import tool
from cora.recipe.features.get_plan.handler import Handler, PlanView, bind
from cora.recipe.features.get_plan.query import GetPlan
from cora.recipe.features.get_plan.route import router

__all__ = [
    "GetPlan",
    "Handler",
    "PlanView",
    "bind",
    "router",
    "tool",
]
