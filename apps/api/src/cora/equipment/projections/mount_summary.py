"""MountSummaryProjection: folds the Mount aggregate's lifecycle +
placement + installation events into the `proj_equipment_mount_summary`
read model that backs operator-facing Mount queries.

Subscribed events:
  - MountRegistered          -> INSERT (status=Active; installed_asset_id=NULL;
                                slot_code, parent_id, placement,
                                drawing from payload)
  - MountDecommissioned      -> UPDATE status=Decommissioned
  - MountPlacementUpdated    -> UPDATE placement
  - MountAssetInstalled      -> UPDATE installed_asset_id = $asset_id
  - MountAssetUninstalled    -> UPDATE installed_asset_id = NULL

All branches idempotent (INSERT uses ON CONFLICT DO NOTHING; UPDATEs
write fixed values per event type so re-application is a no-op).
Mirrors FrameSummaryProjection's shape.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_MOUNT_SQL = """
INSERT INTO proj_equipment_mount_summary
    (mount_id, slot_code, parent_id, placement, drawing,
     installed_asset_id, status, created_at)
VALUES ($1, $2, $3, $4, $5, NULL, 'Active', $6)
ON CONFLICT (mount_id) DO NOTHING
"""

_UPDATE_STATUS_SQL = """
UPDATE proj_equipment_mount_summary
SET status = $2, updated_at = now()
WHERE mount_id = $1
"""

_UPDATE_PLACEMENT_SQL = """
UPDATE proj_equipment_mount_summary
SET placement = $2, updated_at = now()
WHERE mount_id = $1
"""

_UPDATE_INSTALLED_ASSET_SQL = """
UPDATE proj_equipment_mount_summary
SET installed_asset_id = $2, updated_at = now()
WHERE mount_id = $1
"""


class MountSummaryProjection:
    """Maintains the `proj_equipment_mount_summary` read model."""

    name = "proj_equipment_mount_summary"
    subscribed_event_types = frozenset(
        {
            "MountRegistered",
            "MountDecommissioned",
            "MountPlacementUpdated",
            "MountAssetInstalled",
            "MountAssetUninstalled",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "MountRegistered":
                parent_raw = event.payload.get("parent_id")
                parent_id = UUID(parent_raw) if parent_raw else None
                drawing = event.payload.get("drawing")
                drawing_json = json.dumps(drawing) if drawing is not None else None
                await conn.execute(
                    _INSERT_MOUNT_SQL,
                    UUID(event.payload["mount_id"]),
                    event.payload["slot_code"],
                    parent_id,
                    json.dumps(event.payload["placement"]),
                    drawing_json,
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "MountDecommissioned":
                await conn.execute(
                    _UPDATE_STATUS_SQL,
                    UUID(event.payload["mount_id"]),
                    "Decommissioned",
                )
            case "MountPlacementUpdated":
                await conn.execute(
                    _UPDATE_PLACEMENT_SQL,
                    UUID(event.payload["mount_id"]),
                    json.dumps(event.payload["new_placement"]),
                )
            case "MountAssetInstalled":
                await conn.execute(
                    _UPDATE_INSTALLED_ASSET_SQL,
                    UUID(event.payload["mount_id"]),
                    UUID(event.payload["asset_id"]),
                )
            case "MountAssetUninstalled":
                await conn.execute(
                    _UPDATE_INSTALLED_ASSET_SQL,
                    UUID(event.payload["mount_id"]),
                    None,
                )
            case _:
                pass
