"""Vertical slice for the `DeprecateClearanceTemplate` command."""

from cora.safety.features.deprecate_clearance_template import tool
from cora.safety.features.deprecate_clearance_template.command import DeprecateClearanceTemplate
from cora.safety.features.deprecate_clearance_template.decider import decide
from cora.safety.features.deprecate_clearance_template.handler import Handler, bind
from cora.safety.features.deprecate_clearance_template.route import router

__all__ = [
    "DeprecateClearanceTemplate",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
