"""FrameConsumersProjection: tracks references TO a frame (consumers).

A "consumer" is any aggregate that holds a reference to a Frame in a
way that would break if the Frame were decommissioned. Today that
means child Frames only (a Frame's parent_frame_id points at this
frame). Once the Mount aggregate lands, consumers extend to active
Mounts whose `Placement.parent_frame` points at this frame.

The `decommission_frame` slice's longhand handler loads
`load_active_frame_consumers(frame_id) -> tuple[UUID, ...]` from
this projection BEFORE calling the pure decider; the decider raises
`FrameInUseError` if the tuple is non-empty.

Subscribed events:
  - FrameRegistered     -> INSERT (referenced_frame_id=parent_frame_id,
                           consumer_id=this_frame_id, consumer_type='Frame')
                           when parent_frame_id is not None
  - FrameDecommissioned -> DELETE WHERE consumer_id = this_frame_id
                           (Frame consumers go away when they
                           themselves decommission)

The MountRegistered + MountDecommissioned subscriptions land
together with the Mount aggregate to populate Mount-type rows.
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
WHERE consumer_id = $1
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
