"""Vertical slice for the `GetFamily` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.equipment.features import get_family

    q = get_family.GetFamily(family_id=...)
    handler = get_family.bind(deps)
    family = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.get_family import tool
from cora.equipment.features.get_family.handler import FamilyView, Handler, bind
from cora.equipment.features.get_family.query import GetFamily
from cora.equipment.features.get_family.route import router

__all__ = [
    "FamilyView",
    "GetFamily",
    "Handler",
    "bind",
    "router",
    "tool",
]
