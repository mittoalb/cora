"""RunSummaryProjection: folds the Run aggregate's 7 lifecycle events
into the `proj_run_summary` read model that backs `GET /runs`.

Subscribed events (genesis + 6 transitions):
  - RunStarted     -> INSERT (status=Running, name + plan_id +
                              subject_id? + raid? + 6g-c
                              parameter_overrides_present from payload)
  - RunHeld        -> UPDATE status=Held
  - RunResumed     -> UPDATE status=Running
  - RunCompleted   -> UPDATE status=Completed   (terminal)
  - RunAborted     -> UPDATE status=Aborted     (terminal)
  - RunStopped     -> UPDATE status=Stopped     (terminal)
  - RunTruncated   -> UPDATE status=Truncated   (terminal)

All branches idempotent. Genesis-event payload values (plan_id,
subject_id, raid, parameter_overrides_present) land on INSERT and
never change; lifecycle UPDATEs only touch `status`.

`parameter_overrides_present` (Phase 6g-c) is TRUE iff RunStarted's
`parameter_overrides` payload was non-empty (operator customized
parameters at start time vs. just used Plan defaults). The full
overrides + effective_parameters dicts live on the event itself,
loaded on demand via `get_run` fold-on-read; the boolean is the
list-endpoint filter primitive. See
[[project_run_parameters_design]] §6g-c for the locked design and
the future JSONB-column trigger (promote when key-level value
filtering becomes a pilot need).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_RUN_SQL = """
INSERT INTO proj_run_summary
    (run_id, name, plan_id, subject_id, raid, status, created_at,
     parameter_overrides_present)
VALUES ($1, $2, $3, $4, $5, 'Running', $6, $7)
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
            # Forward-compat: pre-6g-c RunStarted payloads have no
            # parameter_overrides key; bool({}) is FALSE so legacy
            # rows backfill cleanly.
            overrides_present = bool(payload.get("parameter_overrides"))
            await conn.execute(
                _INSERT_RUN_SQL,
                UUID(payload["run_id"]),
                payload["name"],
                UUID(payload["plan_id"]),
                subject_id,
                payload.get("raid"),
                datetime.fromisoformat(payload["occurred_at"]),
                overrides_present,
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
