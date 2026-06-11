"""Vertical slice for the `DefineClearanceTemplate` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.safety.features import define_clearance_template

    cmd = define_clearance_template.DefineClearanceTemplate(
        code="...", title="...", facility_code="..."
    )
    handler = define_clearance_template.bind(deps)
    template_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.safety.features.define_clearance_template import tool
from cora.safety.features.define_clearance_template.command import (
    DefineClearanceTemplate,
)
from cora.safety.features.define_clearance_template.decider import decide
from cora.safety.features.define_clearance_template.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.safety.features.define_clearance_template.route import router

__all__ = [
    "DefineClearanceTemplate",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
