"""FrameChildrenProjection: tracks parent_frame_id -> child Frame IDs.

Backs queries that need to walk the Frame tree (cycle defense at
register time, listing children under a node, etc.) without
event-stream replay.

Subscribed events:
  - FrameRegistered     -> INSERT (parent_frame_id, child_frame_id)
                           when parent_frame_id is not None
                           (root frames are skipped; they have no parent)
  - FrameDecommissioned -> DELETE matching row (child no longer counts
                           as a "live" child)

Both idempotent at the projection layer: INSERT uses ON CONFLICT DO
NOTHING; DELETE of a non-existent row is a no-op.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SQL = """
INSERT INTO proj_equipment_frame_children
    (parent_frame_id, child_frame_id, registered_at)
VALUES ($1, $2, $3)
ON CONFLICT (parent_frame_id, child_frame_id) DO NOTHING
"""

_DELETE_BY_CHILD_SQL = """
DELETE FROM proj_equipment_frame_children
WHERE child_frame_id = $1
"""


class FrameChildrenProjection:
    """Maintains the `proj_equipment_frame_children` read model."""

    name = "proj_equipment_frame_children"
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
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "FrameDecommissioned":
                await conn.execute(
                    _DELETE_BY_CHILD_SQL,
                    UUID(event.payload["frame_id"]),
                )
            case _:
                pass
