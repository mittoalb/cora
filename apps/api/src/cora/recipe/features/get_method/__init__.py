"""Vertical slice for the `GetMethod` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.recipe.features import get_method

    q = get_method.GetMethod(method_id=...)
    handler = get_method.bind(deps)
    method = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.get_method import tool
from cora.recipe.features.get_method.handler import Handler, MethodView, bind
from cora.recipe.features.get_method.query import GetMethod
from cora.recipe.features.get_method.route import router

__all__ = [
    "GetMethod",
    "Handler",
    "MethodView",
    "bind",
    "router",
    "tool",
]
