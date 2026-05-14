"""SubjectSummaryProjection: folds the 8 Subject lifecycle events into
the `proj_subject_summary` read model that backs `GET /subjects`.

Status semantics: derived from event TYPE (not payload). Each event
type maps to one status; the projection apply() match-dispatches on
event_type and writes the corresponding status string. All branches
are idempotent (INSERT uses `ON CONFLICT (subject_id) DO NOTHING`;
UPDATEs write the same status value regardless of how many times the
event lands).

Subscribed events:
  - SubjectRegistered -> status=Received  (INSERT)
  - SubjectMounted    -> status=Mounted    (UPDATE)
  - SubjectMeasured   -> status=Measured   (UPDATE)
  - SubjectDismounted -> status=Received   (UPDATE) — 4f re-mount cycle
  - SubjectRemoved    -> status=Removed    (UPDATE)
  - SubjectReturned   -> status=Returned   (UPDATE) — terminal
  - SubjectStored     -> status=Stored     (UPDATE) — terminal
  - SubjectDiscarded  -> status=Discarded  (UPDATE) — terminal

Per the docstring on `cora/subject/aggregates/subject/state.py` the
status field on events is INTENTIONALLY absent from payloads — the
event type IS the status discriminator. This projection mirrors that
convention: status string is hardcoded per match arm rather than
read from `event.payload["status"]`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SUBJECT_SQL = """
INSERT INTO proj_subject_summary
    (subject_id, name, status, created_at)
VALUES ($1, $2, 'Received', $3)
ON CONFLICT (subject_id) DO NOTHING
"""

# Each transition writes a fixed status string. Pulled into a helper
# so each match arm collapses to one parameterized call instead of
# duplicating the UPDATE template seven times.
_UPDATE_STATUS_SQL = """
UPDATE proj_subject_summary
SET status = $2, updated_at = now()
WHERE subject_id = $1
"""


class SubjectSummaryProjection:
    """Maintains the `proj_subject_summary` read model.

    `name` and `subscribed_event_types` are class-level constants (not
    ClassVar-annotated, matching the Projection Protocol's plain-attr
    declaration; identical Python semantics for these immutable values).
    """

    name = "proj_subject_summary"
    subscribed_event_types = frozenset(
        {
            "SubjectRegistered",
            "SubjectMounted",
            "SubjectMeasured",
            "SubjectDismounted",
            "SubjectRemoved",
            "SubjectReturned",
            "SubjectStored",
            "SubjectDiscarded",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        """Dispatch on event_type. INSERT branch is idempotent via
        ON CONFLICT; UPDATE branches write a fixed status value so
        re-application is a no-op. The `case _: pass` is for pyright
        exhaustiveness on `str` (the SQL filter guarantees apply()
        only sees subscribed types in production)."""
        match event.event_type:
            case "SubjectRegistered":
                await conn.execute(
                    _INSERT_SUBJECT_SQL,
                    UUID(event.payload["subject_id"]),
                    event.payload["name"],
                    datetime.fromisoformat(event.payload["occurred_at"]),
                )
            case "SubjectMounted":
                await self._update_status(event, conn, "Mounted")
            case "SubjectMeasured":
                await self._update_status(event, conn, "Measured")
            case "SubjectDismounted":
                # 4f re-mount cycle: dismount returns the Subject to
                # Received status (sample is in the lab, not currently
                # mounted). The mount/dismount cycle can repeat any
                # number of times before terminal disposition.
                await self._update_status(event, conn, "Received")
            case "SubjectRemoved":
                await self._update_status(event, conn, "Removed")
            case "SubjectReturned":
                await self._update_status(event, conn, "Returned")
            case "SubjectStored":
                await self._update_status(event, conn, "Stored")
            case "SubjectDiscarded":
                await self._update_status(event, conn, "Discarded")
            case _:
                pass

    async def _update_status(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
        new_status: str,
    ) -> None:
        await conn.execute(
            _UPDATE_STATUS_SQL,
            UUID(event.payload["subject_id"]),
            new_status,
        )


__all__ = ["SubjectSummaryProjection"]
