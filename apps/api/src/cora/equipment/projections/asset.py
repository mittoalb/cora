"""AssetSummaryProjection: folds the Asset aggregate's lifecycle +
hierarchy + condition events into the `proj_equipment_asset_summary`
read model that backs `GET /assets`.

Subscribed events:
  - AssetRegistered            -> INSERT (lifecycle=Commissioned,
                                  condition=Nominal; level + parent_id
                                  from payload)
  - AssetActivated             -> UPDATE lifecycle=Active
  - AssetDecommissioned        -> UPDATE lifecycle=Decommissioned
  - AssetMaintenanceEntered    -> UPDATE lifecycle=Maintenance
  - AssetRestoredFromMaintenance -> UPDATE lifecycle=Active
  - AssetRelocated             -> UPDATE parent_id=to_parent_id
  - AssetDegraded              -> UPDATE condition=Degraded
  - AssetFaulted               -> UPDATE condition=Faulted
  - AssetRestored              -> UPDATE condition=Nominal

NOT subscribed:
  - AssetFamilyAdded / AssetFamilyRemoved — these describe
    the Asset<->Family join, not the Asset's own state. Belong
    in a future `proj_equipment_asset_capabilities` projection
    (deferred until a list-by-capability query demands it).

All branches idempotent (INSERT uses ON CONFLICT DO NOTHING; UPDATEs
write fixed values per event type so re-application is a no-op).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_ASSET_SQL = """
INSERT INTO proj_equipment_asset_summary
    (asset_id, name, level, lifecycle, condition, parent_id, created_at)
VALUES ($1, $2, $3, 'Commissioned', 'Nominal', $4, $5)
ON CONFLICT (asset_id) DO NOTHING
"""

_UPDATE_LIFECYCLE_SQL = """
UPDATE proj_equipment_asset_summary
SET lifecycle = $2, updated_at = now()
WHERE asset_id = $1
"""

_UPDATE_PARENT_SQL = """
UPDATE proj_equipment_asset_summary
SET parent_id = $2, updated_at = now()
WHERE asset_id = $1
"""

_UPDATE_CONDITION_SQL = """
UPDATE proj_equipment_asset_summary
SET condition = $2, updated_at = now()
WHERE asset_id = $1
"""


class AssetSummaryProjection:
    """Maintains the `proj_equipment_asset_summary` read model."""

    name = "proj_equipment_asset_summary"
    subscribed_event_types = frozenset(
        {
            "AssetRegistered",
            "AssetActivated",
            "AssetDecommissioned",
            "AssetMaintenanceEntered",
            "AssetRestoredFromMaintenance",
            "AssetRelocated",
            "AssetDegraded",
            "AssetFaulted",
            "AssetRestored",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        """Dispatch on event_type. The `case _: pass` is for pyright
        exhaustiveness (the SQL filter guarantees apply() never sees
        unsubscribed types in production)."""
        match event.event_type:
            case "AssetRegistered":
                parent_id_raw = event.payload.get("parent_id")
                parent_id = UUID(parent_id_raw) if parent_id_raw else None
                await conn.execute(
                    _INSERT_ASSET_SQL,
                    UUID(event.payload["asset_id"]),
                    event.payload["name"],
                    event.payload["level"],
                    parent_id,
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "AssetActivated" | "AssetRestoredFromMaintenance":
                await self._update_lifecycle(event, conn, "Active")
            case "AssetDecommissioned":
                await self._update_lifecycle(event, conn, "Decommissioned")
            case "AssetMaintenanceEntered":
                await self._update_lifecycle(event, conn, "Maintenance")
            case "AssetRelocated":
                await conn.execute(
                    _UPDATE_PARENT_SQL,
                    UUID(event.payload["asset_id"]),
                    UUID(event.payload["to_parent_id"]),
                )
            case "AssetDegraded":
                await self._update_condition(event, conn, "Degraded")
            case "AssetFaulted":
                await self._update_condition(event, conn, "Faulted")
            case "AssetRestored":
                await self._update_condition(event, conn, "Nominal")
            case _:
                pass

    async def _update_lifecycle(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
        new_lifecycle: str,
    ) -> None:
        await conn.execute(
            _UPDATE_LIFECYCLE_SQL,
            UUID(event.payload["asset_id"]),
            new_lifecycle,
        )

    async def _update_condition(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
        new_condition: str,
    ) -> None:
        await conn.execute(
            _UPDATE_CONDITION_SQL,
            UUID(event.payload["asset_id"]),
            new_condition,
        )


__all__ = ["AssetSummaryProjection"]
