"""Vertical slice for the `UpdateAssetSettings` command.

Module-as-namespace surface:

    from cora.equipment.features import update_asset_settings

    cmd = update_asset_settings.UpdateAssetSettings(
        asset_id=..., settings_patch={"exposure": 50, "filter": "Cu"}
    )
    handler = update_asset_settings.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

The first slice that consumes `Family.settings_schema`
declarations: the handler loads every
Family assigned to the target Asset, unions their schemas, and
validates the proposed (post-merge) settings against the union via
`jsonschema-rs`. Atomicity is per-Asset (single stream append at
the end); Family schemas are read at decision time and may
change concurrently — we accept the small race because schema
changes are rare and existing settings are NOT auto-revalidated.

Custom handler (NOT make_asset_update_handler) because the
factory only loads the target Asset stream; this slice must
ALSO load N Family streams concurrently to compute the union.
"""

from cora.equipment.features.update_asset_settings import tool
from cora.equipment.features.update_asset_settings.command import UpdateAssetSettings
from cora.equipment.features.update_asset_settings.decider import decide
from cora.equipment.features.update_asset_settings.handler import Handler, bind
from cora.equipment.features.update_asset_settings.route import router

__all__ = [
    "Handler",
    "UpdateAssetSettings",
    "bind",
    "decide",
    "router",
    "tool",
]
