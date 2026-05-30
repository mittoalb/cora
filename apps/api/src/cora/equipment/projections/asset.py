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
  - AssetFamilyAdded / AssetFamilyRemoved: these describe
    the Asset<->Family join, not the Asset's own state. They
    feed the sibling `AssetFamilyMembershipProjection`
    (`proj_equipment_asset_family_membership`).

All branches idempotent (INSERT uses ON CONFLICT DO NOTHING; UPDATEs
write fixed values per event type so re-application is a no-op).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    import asyncpg

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


_SELECT_ASSET_EXISTS_SQL = """
SELECT 1
FROM proj_equipment_asset_summary
WHERE asset_id = $1
"""


async def load_asset_exists(
    pool: asyncpg.Pool | None,
    asset_id: UUID,
) -> bool:
    """Return True iff an Asset row exists for `asset_id`.

    Used by the install_asset handler as a projection precondition:
    if the Asset has no event-store stream (or projection row), the
    decider raises AssetNotFoundForMountError before mutating the
    Mount stream.

    Returns False when `pool` is None (test environments that opt
    out of Postgres; the corresponding install_asset tests construct
    the context directly).

    Reuses the existing proj_equipment_asset_summary table per the
    Mount/Frame Stage-1 design memo intent: no separate asset_lookup
    projection needed.
    """
    if pool is None:
        return False
    row = await pool.fetchrow(_SELECT_ASSET_EXISTS_SQL, asset_id)
    return row is not None


__all__ = ["AssetSummaryProjection", "load_asset_exists"]
