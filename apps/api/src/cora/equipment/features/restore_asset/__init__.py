"""Vertical slice for the `RestoreAsset` command.

Module-as-namespace surface:

    from cora.equipment.features import restore_asset

    cmd = restore_asset.RestoreAsset(asset_id=..., reason="...")
    handler = restore_asset.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

One of three condition-transition slices (degrade / fault /
restore). Mirror of `degrade_asset` with target Nominal.

Naming distinct from `restore_from_maintenance`: that slice
restores a lifecycle state (Maintenance -> Active); this slice
restores a condition state (any -> Nominal). Both verbs share the
"return to baseline" connotation in different dimensions.
"""

from cora.equipment.features.restore_asset import tool
from cora.equipment.features.restore_asset.command import RestoreAsset
from cora.equipment.features.restore_asset.decider import decide
from cora.equipment.features.restore_asset.handler import Handler, bind
from cora.equipment.features.restore_asset.route import router

__all__ = [
    "Handler",
    "RestoreAsset",
    "bind",
    "decide",
    "router",
    "tool",
]
