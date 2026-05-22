"""Vertical slice for the `FaultAsset` command.

Module-as-namespace surface:

    from cora.equipment.features import fault_asset

    cmd = fault_asset.FaultAsset(asset_id=..., reason="...")
    handler = fault_asset.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

One of three condition-transition slices (degrade / fault /
restore). Mirror of `degrade_asset` with target Faulted.
"""

from cora.equipment.features.fault_asset import tool
from cora.equipment.features.fault_asset.command import FaultAsset
from cora.equipment.features.fault_asset.decider import decide
from cora.equipment.features.fault_asset.handler import Handler, bind
from cora.equipment.features.fault_asset.route import router

__all__ = [
    "FaultAsset",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
