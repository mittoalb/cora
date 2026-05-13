"""DatasetSummaryProjection: folds the Dataset aggregate's 2 lifecycle
events into the `proj_data_dataset_summary` read model that backs
`GET /datasets`.

Subscribed events:
  - DatasetRegistered  -> INSERT (status=Registered, name + uri +
                                  producing_run_id? + subject_id?
                                  from genesis payload)
  - DatasetDiscarded   -> UPDATE status=Discarded   (terminal)

Both branches idempotent. Genesis-event payload values
(producing_run_id, subject_id) land on INSERT and never change;
the discard UPDATE only touches `status`. The audit trail of
"what was the producing Run / Subject for this discarded Dataset"
stays visible in the projection.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_DATASET_SQL = """
INSERT INTO proj_data_dataset_summary
    (dataset_id, name, uri, producing_run_id, subject_id, status, created_at)
VALUES ($1, $2, $3, $4, $5, 'Registered', $6)
ON CONFLICT (dataset_id) DO NOTHING
"""

_UPDATE_DISCARDED_SQL = """
UPDATE proj_data_dataset_summary
SET status = 'Discarded', updated_at = now()
WHERE dataset_id = $1
"""


class DatasetSummaryProjection:
    """Maintains the `proj_data_dataset_summary` read model."""

    name = "proj_data_dataset_summary"
    subscribed_event_types = frozenset({"DatasetRegistered", "DatasetDiscarded"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "DatasetRegistered":
                payload = event.payload
                producing_run_id = (
                    UUID(payload["producing_run_id"]) if payload.get("producing_run_id") else None
                )
                subject_id = UUID(payload["subject_id"]) if payload.get("subject_id") else None
                await conn.execute(
                    _INSERT_DATASET_SQL,
                    UUID(payload["dataset_id"]),
                    payload["name"],
                    payload["uri"],
                    producing_run_id,
                    subject_id,
                    datetime.fromisoformat(payload["occurred_at"]),
                )
            case "DatasetDiscarded":
                await conn.execute(
                    _UPDATE_DISCARDED_SQL,
                    UUID(event.payload["dataset_id"]),
                )
            case _:
                pass


__all__ = ["DatasetSummaryProjection"]
