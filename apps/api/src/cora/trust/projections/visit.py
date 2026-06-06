"""VisitSummaryProjection: folds Visit events into the proj_trust_visit_summary
read model that backs `GET /visits`.

Subscribed events:
  - VisitRegistered  -> INSERT (genesis, with planned_* + parent_id + external_refs)
  - VisitArrived     -> UPDATE arrived_at + status='Arrived'
  - VisitStarted     -> UPDATE started_at + status='InProgress'
  - VisitHeld        -> UPDATE status='OnHold' + last_status_reason
  - VisitResumed     -> UPDATE status='InProgress' (last_status_reason preserved)
  - VisitCompleted   -> UPDATE completed_at + status='Completed'
  - VisitCancelled   -> UPDATE completed_at + status='Cancelled' + reason
  - VisitAborted     -> UPDATE completed_at + status='Aborted' + reason
  - VisitVoided      -> UPDATE completed_at + status='Voided' + reason

Per `[[project_template_aggregate_timestamps]]` Path C, statushistory is
NOT inline; a separate proj_trust_visit_status_history projection lands
when needed.

All INSERTs use ON CONFLICT (visit_id) DO NOTHING; all UPDATEs are
naturally idempotent (re-applying the same event matches the same row).
Standard CORA replay-safety pattern.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_SUBSCRIBED: frozenset[str] = frozenset(
    {
        "VisitRegistered",
        "VisitArrived",
        "VisitStarted",
        "VisitHeld",
        "VisitResumed",
        "VisitCompleted",
        "VisitCancelled",
        "VisitAborted",
        "VisitVoided",
    }
)

# 'Planned' is hardcoded because VisitRegistered always folds to
# Planned per the evolver; source-of-truth lives at
# `cora.trust.aggregates.visit.evolver` + `state.VisitStatus.PLANNED`.
_INSERT_SQL = """
INSERT INTO proj_trust_visit_summary (
    visit_id, policy_id, surface_id, type, status,
    planned_start_at, planned_end_at,
    parent_id, external_refs,
    created_at
)
VALUES ($1, $2, $3, $4, 'Planned', $5, $6, $7, $8::jsonb, $9)
ON CONFLICT (visit_id) DO NOTHING
"""

_UPDATE_ARRIVED_SQL = """
UPDATE proj_trust_visit_summary
SET status = 'Arrived', arrived_at = $2, updated_at = now()
WHERE visit_id = $1
"""

_UPDATE_STARTED_SQL = """
UPDATE proj_trust_visit_summary
SET status = 'InProgress', started_at = $2, updated_at = now()
WHERE visit_id = $1
"""

_UPDATE_HELD_SQL = """
UPDATE proj_trust_visit_summary
SET status = 'OnHold', last_status_reason = $2, updated_at = now()
WHERE visit_id = $1
"""

_UPDATE_RESUMED_SQL = """
UPDATE proj_trust_visit_summary
SET status = 'InProgress', updated_at = now()
WHERE visit_id = $1
"""

# Completed / Cancelled / Aborted / Voided share the "terminal status + completed_at"
# shape but differ in whether they record last_status_reason (Cancelled, Aborted,
# Voided do; Completed does not). Separate SQL strings keep the code obvious.
_UPDATE_COMPLETED_SQL = """
UPDATE proj_trust_visit_summary
SET status = 'Completed', completed_at = $2, updated_at = now()
WHERE visit_id = $1
"""

_UPDATE_TERMINAL_WITH_REASON_SQL = """
UPDATE proj_trust_visit_summary
SET status = $2, completed_at = $3, last_status_reason = $4, updated_at = now()
WHERE visit_id = $1
"""


class VisitSummaryProjection:
    """Maintains the `proj_trust_visit_summary` read model."""

    name = "proj_trust_visit_summary"
    subscribed_event_types = _SUBSCRIBED

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type not in _SUBSCRIBED:
            return

        payload = event.payload
        visit_id = UUID(payload["visit_id"])
        occurred_at = datetime.fromisoformat(payload["occurred_at"])

        match event.event_type:
            case "VisitRegistered":
                parent_raw = payload.get("parent_id")
                await conn.execute(
                    _INSERT_SQL,
                    visit_id,
                    UUID(payload["policy_id"]),
                    UUID(payload["surface_id"]),
                    payload["type"],
                    datetime.fromisoformat(payload["planned_start_at"]),
                    datetime.fromisoformat(payload["planned_end_at"]),
                    UUID(parent_raw) if parent_raw is not None else None,
                    json.dumps(payload.get("external_refs", [])),
                    occurred_at,
                )
            case "VisitArrived":
                await conn.execute(_UPDATE_ARRIVED_SQL, visit_id, occurred_at)
            case "VisitStarted":
                await conn.execute(_UPDATE_STARTED_SQL, visit_id, occurred_at)
            case "VisitHeld":
                await conn.execute(_UPDATE_HELD_SQL, visit_id, payload["reason"])
            case "VisitResumed":
                await conn.execute(_UPDATE_RESUMED_SQL, visit_id)
            case "VisitCompleted":
                await conn.execute(_UPDATE_COMPLETED_SQL, visit_id, occurred_at)
            case "VisitCancelled":
                await conn.execute(
                    _UPDATE_TERMINAL_WITH_REASON_SQL,
                    visit_id,
                    "Cancelled",
                    occurred_at,
                    payload["reason"],
                )
            case "VisitAborted":
                await conn.execute(
                    _UPDATE_TERMINAL_WITH_REASON_SQL,
                    visit_id,
                    "Aborted",
                    occurred_at,
                    payload["reason"],
                )
            case "VisitVoided":
                await conn.execute(
                    _UPDATE_TERMINAL_WITH_REASON_SQL,
                    visit_id,
                    "Voided",
                    occurred_at,
                    payload["reason"],
                )
            case _:  # pragma: no cover  # _SUBSCRIBED gate above prevents reaching here
                pass


__all__ = ["VisitSummaryProjection"]
