"""SupplySummaryProjection: folds the Supply aggregate's events into
the `proj_supply_summary` read model that backs `GET /supplies`.

Subscribed events (Phase 10a-a):
  - SupplyRegistered      -> INSERT (status='Unknown', last_status_*=NULL)
  - SupplyMarkedAvailable -> UPDATE status='Available' + last_status_changed_at
                                    + last_status_reason + last_trigger

Phase 10a-b will subscribe to 4 more transition events
(SupplyDegraded / SupplyMarkedUnavailable / SupplyMarkedRecovering /
SupplyRestored), each updating status + the same audit triple.

All branches idempotent. The CHECK constraints on `status` and
`last_trigger` were locked with the full enum values day one (5
statuses + 3 triggers) so 10a-b's transitions land without a
constraint migration.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SUPPLY_SQL = """
INSERT INTO proj_supply_summary
    (supply_id, scope, kind, name, status, registered_at,
     last_status_changed_at, last_status_reason, last_trigger)
VALUES ($1, $2, $3, $4, 'Unknown', $5, NULL, NULL, NULL)
ON CONFLICT (supply_id) DO NOTHING
"""

_UPDATE_AVAILABLE_SQL = """
UPDATE proj_supply_summary
SET status = 'Available',
    last_status_changed_at = $2,
    last_status_reason = $3,
    last_trigger = $4,
    updated_at = now()
WHERE supply_id = $1
"""


class SupplySummaryProjection:
    """Maintains the `proj_supply_summary` read model."""

    name = "proj_supply_summary"
    subscribed_event_types = frozenset(
        {
            "SupplyRegistered",
            "SupplyMarkedAvailable",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "SupplyRegistered":
                await conn.execute(
                    _INSERT_SUPPLY_SQL,
                    UUID(event.payload["supply_id"]),
                    event.payload["scope"],
                    event.payload["kind"],
                    event.payload["name"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "SupplyMarkedAvailable":
                await conn.execute(
                    _UPDATE_AVAILABLE_SQL,
                    UUID(event.payload["supply_id"]),
                    datetime.fromisoformat(event.payload["occurred_at"]),
                    event.payload["reason"],
                    event.payload["trigger"],
                )
            case _:
                pass


__all__ = ["SupplySummaryProjection"]
