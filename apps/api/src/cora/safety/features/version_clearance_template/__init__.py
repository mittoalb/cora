"""Vertical slice for the `VersionClearanceTemplate` command."""

from cora.safety.features.version_clearance_template import tool
from cora.safety.features.version_clearance_template.command import (
    VersionClearanceTemplate,
)
from cora.safety.features.version_clearance_template.decider import decide
from cora.safety.features.version_clearance_template.handler import Handler, bind
from cora.safety.features.version_clearance_template.route import router

__all__ = [
    "Handler",
    "VersionClearanceTemplate",
    "bind",
    "decide",
    "router",
    "tool",
]
