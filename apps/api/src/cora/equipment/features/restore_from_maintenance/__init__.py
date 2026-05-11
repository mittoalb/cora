"""Vertical slice for the `RestoreFromMaintenance` command.

Module-as-namespace surface:

    from cora.equipment.features import restore_from_maintenance

    cmd = restore_from_maintenance.RestoreFromMaintenance(asset_id=...)
    handler = restore_from_maintenance.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Naming deviation noted in `enter_maintenance`'s docstring; same
reasoning applies here.
"""

from cora.equipment.features.restore_from_maintenance import tool
from cora.equipment.features.restore_from_maintenance.command import RestoreFromMaintenance
from cora.equipment.features.restore_from_maintenance.decider import decide
from cora.equipment.features.restore_from_maintenance.handler import Handler, bind
from cora.equipment.features.restore_from_maintenance.route import router

__all__ = [
    "Handler",
    "RestoreFromMaintenance",
    "bind",
    "decide",
    "router",
    "tool",
]
