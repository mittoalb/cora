"""AssetLocationProjection: asset_id -> mount_id (where is this specimen?).

The Asset aggregate does NOT carry an `installed_at: MountId` field
per the design memo's anti-hook: the back-lookup lives in this
projection. Operators query 'where is Asset X right now?' against
this read model; the Mount aggregate's `installed_asset_id` field
is the canonical write-side source of truth.

Subscribed events:
  - MountAssetInstalled   -> INSERT (asset_id, mount_id, installed_at)
                             ON CONFLICT (asset_id) DO UPDATE
                             (re-key the row on re-install at a
                             different mount; same-mount re-install
                             is a no-op)
  - MountAssetUninstalled -> DELETE WHERE asset_id = $1
                             (specimen no longer in any mount)

Both events idempotent at the projection layer. The aggregate's
strict-not-idempotent guards (MountAlreadyOccupied / MountIsEmpty)
fire at command time; this projection's relaxed posture is the
standard CORA replay-safety pattern.

The previously_installed_asset_id field on MountAssetInstalled is
NOT consumed by this projection: the prior occupant's row was
already removed by the preceding MountAssetUninstalled event (the
sequence is uninstall-then-install per the no-implicit-eviction
anti-hook).
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

_UPSERT_SQL = """
INSERT INTO proj_equipment_asset_location
    (asset_id, mount_id, installed_at)
VALUES ($1, $2, $3)
ON CONFLICT (asset_id) DO UPDATE
SET mount_id = EXCLUDED.mount_id,
    installed_at = EXCLUDED.installed_at
"""

_DELETE_BY_ASSET_SQL = """
DELETE FROM proj_equipment_asset_location
WHERE asset_id = $1
"""

_SELECT_BY_ASSET_SQL = """
SELECT mount_id
FROM proj_equipment_asset_location
WHERE asset_id = $1
"""


class AssetLocationProjection:
    """Maintains the `proj_equipment_asset_location` read model."""

    name = "proj_equipment_asset_location"
    subscribed_event_types = frozenset(
        {
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
            case "MountAssetInstalled":
                await conn.execute(
                    _UPSERT_SQL,
                    UUID(event.payload["asset_id"]),
                    UUID(event.payload["mount_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "MountAssetUninstalled":
                await conn.execute(
                    _DELETE_BY_ASSET_SQL,
                    UUID(event.payload["asset_id"]),
                )
            case _:
                pass


async def load_asset_location(
    pool: asyncpg.Pool | None,
    asset_id: UUID,
) -> UUID | None:
    """Return the mount_id currently holding the specimen, or None.

    Used by future cross-aggregate queries that need to answer
    'where is Asset X right now?' without folding the full Mount
    stream. Returns None when the specimen is in no slot, or when
    `pool` is None (test environments that opt out of Postgres).
    """
    if pool is None:
        return None
    row = await pool.fetchrow(_SELECT_BY_ASSET_SQL, asset_id)
    if row is None:
        return None
    return row["mount_id"]
