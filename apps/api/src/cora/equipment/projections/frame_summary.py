"""FrameSummaryProjection: folds the Frame aggregate's lifecycle +
placement events into the `proj_equipment_frame_summary` read model.

Subscribed events:
  - FrameRegistered        -> INSERT (status=Active; name, parent_id,
                              placement from payload)
  - FramePlacementUpdated  -> UPDATE placement
  - FrameDecommissioned    -> UPDATE status=Decommissioned

All branches idempotent (INSERT uses ON CONFLICT DO NOTHING; UPDATEs
write fixed values per event type so re-application is a no-op).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_FRAME_SQL = """
INSERT INTO proj_equipment_frame_summary
    (frame_id, name, parent_id, placement, status, created_at)
VALUES ($1, $2, $3, $4, 'Active', $5)
ON CONFLICT (frame_id) DO NOTHING
"""

_UPDATE_PLACEMENT_SQL = """
UPDATE proj_equipment_frame_summary
SET placement = $2, updated_at = now()
WHERE frame_id = $1
"""

_UPDATE_STATUS_SQL = """
UPDATE proj_equipment_frame_summary
SET status = $2, updated_at = now()
WHERE frame_id = $1
"""


class FrameSummaryProjection:
    """Maintains the `proj_equipment_frame_summary` read model."""

    name = "proj_equipment_frame_summary"
    subscribed_event_types = frozenset(
        {
            "FrameRegistered",
            "FramePlacementUpdated",
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
                parent_raw = event.payload.get("parent_id")
                parent_id = UUID(parent_raw) if parent_raw else None
                placement = event.payload.get("placement")
                placement_json = json.dumps(placement) if placement is not None else None
                await conn.execute(
                    _INSERT_FRAME_SQL,
                    UUID(event.payload["frame_id"]),
                    event.payload["name"],
                    parent_id,
                    placement_json,
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "FramePlacementUpdated":
                await conn.execute(
                    _UPDATE_PLACEMENT_SQL,
                    UUID(event.payload["frame_id"]),
                    json.dumps(event.payload["new_placement"]),
                )
            case "FrameDecommissioned":
                await conn.execute(
                    _UPDATE_STATUS_SQL,
                    UUID(event.payload["frame_id"]),
                    "Decommissioned",
                )
            case _:
                pass
