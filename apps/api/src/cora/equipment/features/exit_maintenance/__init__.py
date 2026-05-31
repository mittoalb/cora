"""Vertical slice for the `ExitMaintenance` command.

Module-as-namespace surface:

    from cora.equipment.features import exit_maintenance

    cmd = exit_maintenance.ExitMaintenance(asset_id=...)
    handler = exit_maintenance.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Naming deviation noted in `enter_maintenance`'s docstring; same
reasoning applies here.
"""

from cora.equipment.features.exit_maintenance import tool
from cora.equipment.features.exit_maintenance.command import ExitMaintenance
from cora.equipment.features.exit_maintenance.decider import decide
from cora.equipment.features.exit_maintenance.handler import Handler, bind
from cora.equipment.features.exit_maintenance.route import router

__all__ = [
    "ExitMaintenance",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
