"""FrameConsumersProjection: tracks references TO a frame (consumers).

A "consumer" is any aggregate that holds a reference to a Frame in a
way that would break if the Frame were decommissioned. Two consumer
types today:
  - Frame: a child Frame's `parent_frame_id` points at this frame.
  - Mount: an active Mount's `placement.parent_frame` points at this
    frame.

The `decommission_frame` slice's longhand handler loads
`load_active_frame_consumers(frame_id) -> tuple[UUID, ...]` from
this projection BEFORE calling the pure decider; the decider raises
`FrameInUseError` if the tuple is non-empty.

Subscribed events:
  - FrameRegistered        -> INSERT (referenced_frame_id=parent_frame_id,
                              consumer_id=this_frame_id, consumer_type='Frame')
                              when parent_frame_id is not None
  - FrameDecommissioned    -> DELETE WHERE consumer_id = this_frame_id
                              (Frame consumers go away when they
                              themselves decommission)
  - MountRegistered        -> INSERT (referenced_frame_id=placement.parent_frame,
                              consumer_id=mount_id, consumer_type='Mount')
  - MountDecommissioned    -> DELETE WHERE consumer_id = mount_id
                              (Mount consumers go away when they
                              themselves decommission)

The projection treats `consumer_id` as the polymorphic identifier
across both consumer types; DELETE-by-consumer-id removes both
Frame- and Mount-type rows that share that consumer id (in practice
mount ids and frame ids do not collide since both are UUIDs from a
single id generator).

Note: `MountPlacementUpdated` is NOT subscribed today. If a future
slice ever allows changing `placement.parent_frame` post-registration,
the projection must subscribe MountPlacementUpdated and re-key the
referenced_frame_id; not in v1 since update_placement keeps the
parent_frame fixed (the decider validates new_placement.parent_frame
matches the existing parent_frame_id).
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
INSERT INTO proj_equipment_frame_consumers
    (referenced_frame_id, consumer_id, consumer_type, registered_at)
VALUES ($1, $2, $3, $4)
ON CONFLICT (referenced_frame_id, consumer_id, consumer_type) DO NOTHING
"""

_DELETE_BY_CONSUMER_SQL = """
DELETE FROM proj_equipment_frame_consumers
WHERE consumer_id = $1 AND consumer_type = $2
"""

_SELECT_ACTIVE_CONSUMERS_SQL = """
SELECT consumer_id
FROM proj_equipment_frame_consumers
WHERE referenced_frame_id = $1
"""


class FrameConsumersProjection:
    """Maintains the `proj_equipment_frame_consumers` read model."""

    name = "proj_equipment_frame_consumers"
    subscribed_event_types = frozenset(
        {
            "FrameRegistered",
            "FrameDecommissioned",
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
            case "FrameRegistered":
                parent_raw = event.payload.get("parent_frame_id")
                if parent_raw is None:
                    return
                await conn.execute(
                    _INSERT_SQL,
                    UUID(parent_raw),
                    UUID(event.payload["frame_id"]),
                    "Frame",
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "FrameDecommissioned":
                await conn.execute(
                    _DELETE_BY_CONSUMER_SQL,
                    UUID(event.payload["frame_id"]),
                    "Frame",
                )
            case "MountRegistered":
                placement = event.payload["placement"]
                referenced_frame_id = UUID(placement["parent_frame"])
                await conn.execute(
                    _INSERT_SQL,
                    referenced_frame_id,
                    UUID(event.payload["mount_id"]),
                    "Mount",
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "MountDecommissioned":
                await conn.execute(
                    _DELETE_BY_CONSUMER_SQL,
                    UUID(event.payload["mount_id"]),
                    "Mount",
                )
            case _:
                pass


async def load_active_frame_consumers(
    pool: asyncpg.Pool | None,
    frame_id: UUID,
) -> tuple[UUID, ...]:
    """Return the currently-active consumer IDs that reference `frame_id`.

    Used by the decommission_frame handler as a projection precondition:
    if the returned tuple is non-empty, the decider raises
    `FrameInUseError`.

    Returns an empty tuple when `pool` is None (test environments
    that opt out of Postgres; the corresponding decommission_frame
    tests construct the context directly).
    """
    if pool is None:
        return ()
    rows = await pool.fetch(_SELECT_ACTIVE_CONSUMERS_SQL, frame_id)
    return tuple(row["consumer_id"] for row in rows)
