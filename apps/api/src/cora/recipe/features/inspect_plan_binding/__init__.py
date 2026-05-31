"""Vertical slice for the `InspectPlanBinding` query.

Module-as-namespace surface:

    from cora.recipe.features import inspect_plan_binding

    q = inspect_plan_binding.InspectPlanBinding(
        practice_id=..., asset_ids=frozenset({...}),
    )
    handler = inspect_plan_binding.bind(deps)
    view = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.inspect_plan_binding import tool
from cora.recipe.features.inspect_plan_binding.handler import Handler, bind
from cora.recipe.features.inspect_plan_binding.query import InspectPlanBinding
from cora.recipe.features.inspect_plan_binding.route import router
from cora.recipe.features.inspect_plan_binding.view import (
    BindingStatus,
    CandidateAsset,
    InspectPlanBindingView,
    MissingAffordanceCandidates,
    WiredAsset,
)

__all__ = [
    "BindingStatus",
    "CandidateAsset",
    "Handler",
    "InspectPlanBinding",
    "InspectPlanBindingView",
    "MissingAffordanceCandidates",
    "WiredAsset",
    "bind",
    "router",
    "tool",
]
