"""MountChildrenProjection: parent_mount_id -> active child Mount IDs.

Backs the `decommission_mount` slice's projection precondition: a
parent Mount cannot be decommissioned while it still has active
child Mounts (no cascade-decommission per the design anti-hook).

Subscribed events:
  - MountRegistered     -> INSERT (parent_mount_id, child_mount_id)
                           when parent_mount_id is not None
                           (top-level mounts are skipped)
  - MountDecommissioned -> DELETE matching row (child no longer
                           counts as a 'live' child of its parent)

Both idempotent at the projection layer: INSERT uses ON CONFLICT DO
NOTHING; DELETE of a non-existent row is a no-op.
Mirrors FrameChildrenProjection's shape.
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

_INSERT_SQL = """
INSERT INTO proj_equipment_mount_children
    (parent_mount_id, child_mount_id, registered_at)
VALUES ($1, $2, $3)
ON CONFLICT (parent_mount_id, child_mount_id) DO NOTHING
"""

_DELETE_BY_CHILD_SQL = """
DELETE FROM proj_equipment_mount_children
WHERE child_mount_id = $1
"""

_SELECT_ACTIVE_CHILDREN_SQL = """
SELECT child_mount_id
FROM proj_equipment_mount_children
WHERE parent_mount_id = $1
"""


class MountChildrenProjection:
    """Maintains the `proj_equipment_mount_children` read model."""

    name = "proj_equipment_mount_children"
    subscribed_event_types = frozenset(
        {
            "MountRegistered",
            "MountDecommissioned",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "MountRegistered":
                parent_raw = event.payload.get("parent_mount_id")
                if parent_raw is None:
                    return
                await conn.execute(
                    _INSERT_SQL,
                    UUID(parent_raw),
                    UUID(event.payload["mount_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "MountDecommissioned":
                await conn.execute(
                    _DELETE_BY_CHILD_SQL,
                    UUID(event.payload["mount_id"]),
                )
            case _:
                pass


async def load_active_mount_children(
    pool: asyncpg.Pool,
    parent_mount_id: UUID,
) -> tuple[UUID, ...]:
    """Return the currently-active child mount IDs of `parent_mount_id`.

    Used by the decommission_mount handler as a projection
    precondition: if the returned tuple is non-empty, the decider
    raises MountHasActiveChildrenError.
    """
    rows = await pool.fetch(_SELECT_ACTIVE_CHILDREN_SQL, parent_mount_id)
    return tuple(row["child_mount_id"] for row in rows)
