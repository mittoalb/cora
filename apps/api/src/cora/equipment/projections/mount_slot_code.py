"""MountSlotCodeProjection: slot_code -> mount_id lookup.

Backs the `register_mount` slice's projection precondition: slot
codes must be unique across all Active Mounts (a register attempt
with a colliding slot_code raises MountAlreadyExistsError at the
handler before reaching the decider).

Subscribed events:
  - MountRegistered     -> INSERT (slot_code, mount_id, registered_at)
                           with ON CONFLICT DO NOTHING for replay safety
  - MountDecommissioned -> DELETE WHERE mount_id = $1  (a
                           Decommissioned slot_code becomes available
                           for re-registration; the row goes away)

Both events are idempotent at the projection layer. The decider's
strict-not-idempotent guard (MountAlreadyExists fires on the second
register against an existing stream) is enforced at the aggregate
layer; this projection only enforces slot-code uniqueness at the
handler-precondition layer.
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
INSERT INTO proj_equipment_mount_slot_code
    (slot_code, mount_id, registered_at)
VALUES ($1, $2, $3)
ON CONFLICT (slot_code) DO NOTHING
"""

_DELETE_BY_MOUNT_SQL = """
DELETE FROM proj_equipment_mount_slot_code
WHERE mount_id = $1
"""

_SELECT_BY_SLOT_CODE_SQL = """
SELECT mount_id
FROM proj_equipment_mount_slot_code
WHERE slot_code = $1
"""


class MountSlotCodeProjection:
    """Maintains the `proj_equipment_mount_slot_code` read model."""

    name = "proj_equipment_mount_slot_code"
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
                await conn.execute(
                    _INSERT_SQL,
                    event.payload["slot_code"],
                    UUID(event.payload["mount_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "MountDecommissioned":
                await conn.execute(
                    _DELETE_BY_MOUNT_SQL,
                    UUID(event.payload["mount_id"]),
                )
            case _:
                pass


async def load_mount_id_by_slot_code(
    pool: asyncpg.Pool,
    slot_code: str,
) -> UUID | None:
    """Return the mount_id for an Active slot_code, or None when free.

    Used by the register_mount handler as a projection precondition:
    if the returned UUID is non-None, the handler raises
    MountAlreadyExistsError before reaching the pure decider (slot
    code collision).
    """
    row = await pool.fetchrow(_SELECT_BY_SLOT_CODE_SQL, slot_code)
    if row is None:
        return None
    return row["mount_id"]
