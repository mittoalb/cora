"""Vertical slice for the `GetPractice` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.recipe.features import get_practice

    q = get_practice.GetPractice(practice_id=...)
    handler = get_practice.bind(deps)
    practice = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.get_practice import tool
from cora.recipe.features.get_practice.handler import Handler, bind
from cora.recipe.features.get_practice.query import GetPractice
from cora.recipe.features.get_practice.route import router

__all__ = [
    "GetPractice",
    "Handler",
    "bind",
    "router",
    "tool",
]
