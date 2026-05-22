"""Vertical slice for the `DegradeAsset` command.

Module-as-namespace surface:

    from cora.equipment.features import degrade_asset

    cmd = degrade_asset.DegradeAsset(asset_id=..., reason="...")
    handler = degrade_asset.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

One of three condition-transition slices (degrade / fault /
restore). Each slice moves to a fixed target condition from
ANY source (target-state semantics, not source-conditional). Reason
is required free text validated 1-500 chars at the API boundary.
"""

from cora.equipment.features.degrade_asset import tool
from cora.equipment.features.degrade_asset.command import DegradeAsset
from cora.equipment.features.degrade_asset.decider import decide
from cora.equipment.features.degrade_asset.handler import Handler, bind
from cora.equipment.features.degrade_asset.route import router

__all__ = [
    "DegradeAsset",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
