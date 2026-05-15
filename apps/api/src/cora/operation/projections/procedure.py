"""ProcedureSummaryProjection: folds the Procedure aggregate's events
into the `proj_operation_procedure_summary` read model that backs
`GET /procedures`.

Subscribed events:
  - ProcedureRegistered          -> INSERT (status='Defined', last_status_*=NULL,
                                            interrupted_at=NULL, steps_logbook_id=NULL)
  - ProcedureStarted             -> UPDATE status='Running'   + status-change ts
  - ProcedureCompleted           -> UPDATE status='Completed' + status-change ts
  - ProcedureAborted             -> UPDATE status='Aborted'   + status-change ts
                                                              + last_status_reason
  - ProcedureTruncated           -> UPDATE status='Truncated' + status-change ts
                                                              + last_status_reason
                                                              + interrupted_at
  - ProcedureStepsLogbookOpened  -> UPDATE steps_logbook_id (status NOT touched;
                                                             logbook is orthogonal
                                                             to lifecycle)

The 4 status-change UPDATEs share the same SQL shape (status literal +
status-change timestamp + optional reason); per-event arms differ only
in which status string + which payload fields they pull. A future
parameterized `_UPDATE_STATUS_SQL` hoist (mirroring proj_supply_summary's
post-10a-b cleanup) becomes worthwhile when a 5th status-change arm
lands -- today the 4 arms keep the dispatch readable.

All branches idempotent. The CHECK constraint on `status` is locked
with the full enum values day one (5 statuses) so no future migration
is needed even if Held/Resumed land later.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_PROCEDURE_SQL = """
INSERT INTO proj_operation_procedure_summary
    (procedure_id, name, kind, target_asset_ids, parent_run_id, status,
     steps_logbook_id, registered_at,
     last_status_changed_at, last_status_reason, interrupted_at)
VALUES ($1, $2, $3, $4::uuid[], $5, 'Defined', NULL, $6, NULL, NULL, NULL)
ON CONFLICT (procedure_id) DO NOTHING
"""

_UPDATE_STARTED_SQL = """
UPDATE proj_operation_procedure_summary
SET status = 'Running',
    last_status_changed_at = $2,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_COMPLETED_SQL = """
UPDATE proj_operation_procedure_summary
SET status = 'Completed',
    last_status_changed_at = $2,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_ABORTED_SQL = """
UPDATE proj_operation_procedure_summary
SET status = 'Aborted',
    last_status_changed_at = $2,
    last_status_reason = $3,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_TRUNCATED_SQL = """
UPDATE proj_operation_procedure_summary
SET status = 'Truncated',
    last_status_changed_at = $2,
    last_status_reason = $3,
    interrupted_at = $4,
    updated_at = now()
WHERE procedure_id = $1
"""

_UPDATE_STEPS_LOGBOOK_OPENED_SQL = """
UPDATE proj_operation_procedure_summary
SET steps_logbook_id = $2,
    updated_at = now()
WHERE procedure_id = $1
"""


class ProcedureSummaryProjection:
    """Maintains the `proj_operation_procedure_summary` read model."""

    name = "proj_operation_procedure_summary"
    subscribed_event_types = frozenset(
        {
            "ProcedureRegistered",
            "ProcedureStarted",
            "ProcedureCompleted",
            "ProcedureAborted",
            "ProcedureTruncated",
            "ProcedureStepsLogbookOpened",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "ProcedureRegistered":
            payload = event.payload
            target_asset_ids = [UUID(a) for a in payload.get("target_asset_ids", [])]
            raw_parent = payload.get("parent_run_id")
            parent_run_id = UUID(raw_parent) if raw_parent is not None else None
            await conn.execute(
                _INSERT_PROCEDURE_SQL,
                UUID(payload["procedure_id"]),
                payload["name"],
                payload["kind"],
                target_asset_ids,
                parent_run_id,
                datetime.fromisoformat(payload["occurred_at"]),
            )
            return

        if event.event_type == "ProcedureStarted":
            await conn.execute(
                _UPDATE_STARTED_SQL,
                UUID(event.payload["procedure_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "ProcedureCompleted":
            await conn.execute(
                _UPDATE_COMPLETED_SQL,
                UUID(event.payload["procedure_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return

        if event.event_type == "ProcedureAborted":
            await conn.execute(
                _UPDATE_ABORTED_SQL,
                UUID(event.payload["procedure_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
                event.payload["reason"],
            )
            return

        if event.event_type == "ProcedureTruncated":
            raw_interrupted_at = event.payload.get("interrupted_at")
            interrupted_at = (
                datetime.fromisoformat(raw_interrupted_at)
                if raw_interrupted_at is not None
                else None
            )
            await conn.execute(
                _UPDATE_TRUNCATED_SQL,
                UUID(event.payload["procedure_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
                event.payload["reason"],
                interrupted_at,
            )
            return

        if event.event_type == "ProcedureStepsLogbookOpened":
            await conn.execute(
                _UPDATE_STEPS_LOGBOOK_OPENED_SQL,
                UUID(event.payload["procedure_id"]),
                UUID(event.payload["logbook_id"]),
            )
            return

        # Unsubscribed event type (defensive; the worker shouldn't
        # deliver them given subscribed_event_types).
        return


__all__ = ["ProcedureSummaryProjection"]
