"""Vertical slice for the `GetClearanceTemplate` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.safety.features import get_clearance_template

    q = get_clearance_template.GetClearanceTemplate(template_id=...)
    handler = get_clearance_template.bind(deps)
    template = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.safety.features.get_clearance_template import tool
from cora.safety.features.get_clearance_template.handler import Handler, bind
from cora.safety.features.get_clearance_template.query import GetClearanceTemplate
from cora.safety.features.get_clearance_template.route import router

__all__ = [
    "GetClearanceTemplate",
    "Handler",
    "bind",
    "router",
    "tool",
]
