"""Vertical slice for the `EnterAssetMaintenance` command.

Module-as-namespace surface:

    from cora.equipment.features import enter_asset_maintenance

    cmd = enter_asset_maintenance.EnterAssetMaintenance(asset_id=...)
    handler = enter_asset_maintenance.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Naming deviation: this slice (and its sibling `exit_asset_maintenance`)
break the `<verb>_<aggregate>` convention used elsewhere in Equipment
(`activate_asset`, `decommission_asset`, `relocate_asset`,
`register_asset`). The aggregate context is carried by the URL prefix
`/assets/{asset_id}/...` and the command/event/error names that all
include `Asset`. Forcing the suffix would yield
`enter_asset_maintenance_asset` / `exit_asset_maintenance_asset`, which
read worse than the deviation.
"""

from cora.equipment.features.enter_asset_maintenance import tool
from cora.equipment.features.enter_asset_maintenance.command import EnterAssetMaintenance
from cora.equipment.features.enter_asset_maintenance.decider import decide
from cora.equipment.features.enter_asset_maintenance.handler import Handler, bind
from cora.equipment.features.enter_asset_maintenance.route import router

__all__ = [
    "EnterAssetMaintenance",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
