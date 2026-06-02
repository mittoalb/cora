"""Vertical slice for the `ExitAssetMaintenance` command.

Module-as-namespace surface:

    from cora.equipment.features import exit_asset_maintenance

    cmd = exit_asset_maintenance.ExitAssetMaintenance(asset_id=...)
    handler = exit_asset_maintenance.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Naming deviation noted in `enter_asset_maintenance`'s docstring; same
reasoning applies here.
"""

from cora.equipment.features.exit_asset_maintenance import tool
from cora.equipment.features.exit_asset_maintenance.command import ExitAssetMaintenance
from cora.equipment.features.exit_asset_maintenance.decider import decide
from cora.equipment.features.exit_asset_maintenance.handler import Handler, bind
from cora.equipment.features.exit_asset_maintenance.route import router

__all__ = [
    "ExitAssetMaintenance",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
