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

## Cross-stream uniqueness on (scope, kind, name)

The migration's `proj_supply_summary_address_uq` UNIQUE INDEX on
`(scope, kind, name)` enforces cross-stream uniqueness at the read
side (the aggregate cannot enforce cross-stream invariants without
DCB per [[project_deferred]]). When two operators register supplies
with the same (scope, kind, name), the second `SupplyRegistered`
event lands in the event store cleanly (no decider gate), but its
projection INSERT raises `asyncpg.UniqueViolationError`.

Day-one operational handling: catch the unique-violation, log a
structured WARN, and return successfully so the projection bookmark
advances and the worker keeps running. The duplicate Supply event
sits in the event log as a permanent audit-record of the operator
mistake; the projection has only the first row. Operators can
discover the issue via list_supplies + reconcile via the future
`deregister_supply` slice (Watch item 10 in the design memo) or via
DCB-backed pre-check at the decider (Watch item 7).

Without this catch the worker would stall on the first duplicate,
blocking ALL Supply projection progress including transitions on
unrelated supplies.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

import asyncpg

from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_log = get_logger(__name__)

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
                # Wrap the INSERT in a SAVEPOINT (asyncpg's nested
                # `conn.transaction()`) so a UniqueViolation on
                # (scope, kind, name) rolls back ONLY the inner write.
                # The worker's outer batch transaction stays clean and
                # subsequent applies + the bookmark advance can
                # proceed. Without the SAVEPOINT, asyncpg raises
                # InFailedSQLTransactionError on the next SQL.
                try:
                    async with conn.transaction():
                        await conn.execute(
                            _INSERT_SUPPLY_SQL,
                            UUID(event.payload["supply_id"]),
                            event.payload["scope"],
                            event.payload["kind"],
                            event.payload["name"],
                            datetime.fromisoformat(event.payload["occurred_at"]),
                        )
                except asyncpg.UniqueViolationError:
                    # Cross-stream duplicate on (scope, kind, name) — see
                    # module docstring. Swallow + log so the worker keeps
                    # running. The duplicate event stays in the event log
                    # as audit; only one projection row exists for the
                    # address.
                    _log.warning(
                        "supply_summary_projection.duplicate_address_skipped",
                        supply_id=event.payload["supply_id"],
                        scope=event.payload["scope"],
                        kind=event.payload["kind"],
                        name=event.payload["name"],
                        event_id=str(event.event_id),
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
