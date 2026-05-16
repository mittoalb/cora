"""Vertical slice for the `GetCaution` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.caution.features import get_caution

    q = get_caution.GetCaution(caution_id=...)
    handler = get_caution.bind(deps)
    caution = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.caution.features.get_caution import tool
from cora.caution.features.get_caution.handler import Handler, bind
from cora.caution.features.get_caution.query import GetCaution
from cora.caution.features.get_caution.route import router

__all__ = [
    "GetCaution",
    "Handler",
    "bind",
    "router",
    "tool",
]
