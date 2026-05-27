"""SupplySummaryProjection: folds the Supply aggregate's events into
the `proj_supply_summary` read model that backs `GET /supplies`.

Subscribed events:
  - SupplyRegistered         -> INSERT (status='Unknown', last_status_*=NULL)
  - SupplyMarkedAvailable    -> UPDATE status='Available'     + audit triple
  - SupplyDegraded           -> UPDATE status='Degraded'      + audit triple
  - SupplyMarkedUnavailable  -> UPDATE status='Unavailable'   + audit triple
  - SupplyMarkedRecovering   -> UPDATE status='Recovering'    + audit triple
  - SupplyRestored           -> UPDATE status='Available'     + audit triple
  - SupplyDeregistered       -> UPDATE status='Decommissioned' + audit triple

All transition arms run a single parameterized `_UPDATE_STATUS_SQL`
with status as $5: the SQL shape is identical across all 6
transitions (status literal + audit triple), so the per-transition
SQL constants were hoisted here. The status string comes from a
per-event-type lookup mirroring `from_stored` in events.py.

All branches idempotent. The status CHECK constraint covers all 6
status values after the Decommissioned-widening migration ships per
[[project_deregister_supply_design]]; last_trigger CHECK covers the
3 trigger values locked day one.

## Cross-stream uniqueness on (scope, kind, name)

The migration's `proj_supply_summary_address_uq` UNIQUE INDEX on
`(scope, kind, name)` enforces cross-stream uniqueness at the read
side (the aggregate cannot enforce cross-stream invariants without
DCB per [[project_deferred]]). The index is PARTIAL on
`WHERE status != 'Decommissioned'`: Decommissioned rows do not count
toward uniqueness, so an operator who deregisters a mistaken Supply
can re-register at the same (scope, kind, name) address with a fresh
supply_id. This is the load-bearing affordance the design memo
[[project_deregister_supply_design]] documents.

When two operators concurrently register supplies with the same
(scope, kind, name) BOTH in active states, the second
`SupplyRegistered` event lands in the event store cleanly (no
decider gate), but its projection INSERT raises
`asyncpg.UniqueViolationError`. Day-one operational handling: catch
the unique-violation, log a structured WARN, and return successfully
so the projection bookmark advances and the worker keeps running.
The duplicate Supply event sits in the event log as a permanent
audit-record of the operator mistake; the projection has only the
first row. Operators de-register one via `deregister_supply`, which
moves it to `Decommissioned`; the partial UNIQUE INDEX then permits
re-registering the address.

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

_UPDATE_STATUS_SQL = """
UPDATE proj_supply_summary
SET status = $5,
    last_status_changed_at = $2,
    last_status_reason = $3,
    last_trigger = $4,
    updated_at = now()
WHERE supply_id = $1
"""

# Per-event-type status mapping for the parameterized UPDATE. Mirrors
# the evolver's per-arm hardcoding; keeps the projection's status
# values in lockstep with the FSM lock in [[project_supply_design]].
_TRANSITION_STATUS: dict[str, str] = {
    "SupplyMarkedAvailable": "Available",
    "SupplyDegraded": "Degraded",
    "SupplyMarkedUnavailable": "Unavailable",
    "SupplyMarkedRecovering": "Recovering",
    "SupplyRestored": "Available",
    # Deploy migration `20260527160000_widen_proj_supply_summary_for_deregister`
    # BEFORE rolling out code that emits SupplyDeregistered: the older
    # status CHECK constraint rejects 'Decommissioned' and stalls the
    # projection worker on the first such event.
    "SupplyDeregistered": "Decommissioned",
}


class SupplySummaryProjection:
    """Maintains the `proj_supply_summary` read model."""

    name = "proj_supply_summary"
    # Derived from `_TRANSITION_STATUS.keys()` so adding a 6th transition
    # event day-2 needs only the dict entry — both subscription and
    # dispatch advance in lockstep.
    subscribed_event_types = frozenset({"SupplyRegistered"} | _TRANSITION_STATUS.keys())

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "SupplyRegistered":
            # Wrap the INSERT in a SAVEPOINT (asyncpg's nested
            # `conn.transaction()`) so a UniqueViolation on
            # (scope, kind, name) rolls back ONLY the inner write.
            # The worker's outer batch transaction stays clean and
            # subsequent applies + the bookmark advance can proceed.
            # Without the SAVEPOINT, asyncpg raises
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
            return

        if event.event_type in _TRANSITION_STATUS:
            # All 6 transition events (MarkedAvailable / Degraded /
            # MarkedUnavailable / MarkedRecovering / Restored /
            # Deregistered) share the same UPDATE shape; status comes
            # from the lookup.
            await conn.execute(
                _UPDATE_STATUS_SQL,
                UUID(event.payload["supply_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
                event.payload["reason"],
                event.payload["trigger"],
                _TRANSITION_STATUS[event.event_type],
            )
            return

        # Unsubscribed event types (defensive — the worker shouldn't
        # deliver them given subscribed_event_types, but the dispatch
        # is no-op-on-foreign-event-type as a safety net).
        return


__all__ = ["SupplySummaryProjection"]
