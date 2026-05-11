"""Vertical slice for the `EnterMaintenance` command.

Module-as-namespace surface:

    from cora.equipment.features import enter_maintenance

    cmd = enter_maintenance.EnterMaintenance(asset_id=...)
    handler = enter_maintenance.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Naming deviation: this slice (and its sibling `restore_from_maintenance`)
break the `<verb>_<aggregate>` convention used elsewhere in Equipment
(`activate_asset`, `decommission_asset`, `relocate_asset`,
`register_asset`). The aggregate context is carried by the URL prefix
`/assets/{asset_id}/...` and the command/event/error names that all
include `Asset`. Forcing the suffix would yield
`enter_maintenance_asset` / `restore_asset_from_maintenance`, which
read worse than the deviation.
"""

from cora.equipment.features.enter_maintenance import tool
from cora.equipment.features.enter_maintenance.command import EnterMaintenance
from cora.equipment.features.enter_maintenance.decider import decide
from cora.equipment.features.enter_maintenance.handler import Handler, bind
from cora.equipment.features.enter_maintenance.route import router

__all__ = [
    "EnterMaintenance",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
