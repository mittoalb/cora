"""RunSummaryProjection: folds the Run aggregate's 7 lifecycle events
into the `proj_run_summary` read model that backs `GET /runs`.

Subscribed events (genesis + 6 transitions):
  - RunStarted     -> INSERT (status=Running, name + plan_id +
                              subject_id? + raid? from payload)
  - RunHeld        -> UPDATE status=Held
  - RunResumed     -> UPDATE status=Running
  - RunCompleted   -> UPDATE status=Completed   (terminal)
  - RunAborted     -> UPDATE status=Aborted     (terminal)
  - RunStopped     -> UPDATE status=Stopped     (terminal)
  - RunTruncated   -> UPDATE status=Truncated   (terminal)

All branches idempotent. Genesis-event payload values (plan_id,
subject_id, raid) land on INSERT and never change; lifecycle UPDATEs
only touch `status`. Match-or pattern groups the 5 status-only
UPDATEs (Held, Resumed, and the 4 terminal transitions all fold to
distinct status strings via the event TYPE).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_RUN_SQL = """
INSERT INTO proj_run_summary
    (run_id, name, plan_id, subject_id, raid, status, created_at)
VALUES ($1, $2, $3, $4, $5, 'Running', $6)
ON CONFLICT (run_id) DO NOTHING
"""

_UPDATE_STATUS_SQL = """
UPDATE proj_run_summary
SET status = $2, updated_at = now()
WHERE run_id = $1
"""

_EVENT_TO_STATUS = {
    "RunHeld": "Held",
    "RunResumed": "Running",
    "RunCompleted": "Completed",
    "RunAborted": "Aborted",
    "RunStopped": "Stopped",
    "RunTruncated": "Truncated",
}


class RunSummaryProjection:
    """Maintains the `proj_run_summary` read model."""

    name = "proj_run_summary"
    subscribed_event_types = frozenset(
        {
            "RunStarted",
            "RunHeld",
            "RunResumed",
            "RunCompleted",
            "RunAborted",
            "RunStopped",
            "RunTruncated",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "RunStarted":
            payload = event.payload
            subject_id = UUID(payload["subject_id"]) if payload.get("subject_id") else None
            await conn.execute(
                _INSERT_RUN_SQL,
                UUID(payload["run_id"]),
                payload["name"],
                UUID(payload["plan_id"]),
                subject_id,
                payload.get("raid"),
                datetime.fromisoformat(payload["occurred_at"]),
            )
            return
        new_status = _EVENT_TO_STATUS.get(event.event_type)
        if new_status is None:
            return
        await conn.execute(
            _UPDATE_STATUS_SQL,
            UUID(event.payload["run_id"]),
            new_status,
        )


__all__ = ["RunSummaryProjection"]
