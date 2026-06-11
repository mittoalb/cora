"""EditionSummaryProjection: folds Edition lifecycle events into
`proj_data_edition_summary`.

Subscribed events (all 6, day-one):

  - EditionRegistered      -> INSERT ON CONFLICT DO NOTHING
  - EditionDatasetAdded    -> UPDATE dataset_ids = array_append (no-op
                              when already present; the decider's
                              strict-not-idempotent guard catches re-add)
  - EditionDatasetRemoved  -> UPDATE dataset_ids = array_remove
  - EditionSealed          -> UPDATE status, content_hash,
                              publisher_facility_code, publication_year,
                              license, sealed_at, sealed_by
  - EditionPublished       -> UPDATE status, external_pid_*,
                              published_content_hash, published_at,
                              published_by
  - EditionWithdrawn       -> UPDATE status, withdrawal_reason,
                              withdrawn_at, withdrawn_by

ON CONFLICT semantics: genesis INSERT uses `ON CONFLICT (edition_id)
DO NOTHING` for stream-id idempotency. Subsequent UPDATEs are
keyed on (edition_id) directly.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from uuid import UUID

from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_log = get_logger(__name__)

_INSERT_EDITION_SQL = """
INSERT INTO proj_data_edition_summary
    (edition_id, kind, title, dataset_ids, creators, license,
     publication_year, publisher_facility_code, status,
     registered_at, registered_by)
VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, 'Registered', $9, $10)
ON CONFLICT (edition_id) DO NOTHING
"""

_ADD_DATASET_SQL = """
UPDATE proj_data_edition_summary
SET dataset_ids = (
        SELECT ARRAY(SELECT DISTINCT unnest(array_append(dataset_ids, $2)))
    ),
    updated_at = now()
WHERE edition_id = $1
"""

_REMOVE_DATASET_SQL = """
UPDATE proj_data_edition_summary
SET dataset_ids = array_remove(dataset_ids, $2),
    updated_at = now()
WHERE edition_id = $1
"""

_SEAL_EDITION_SQL = """
UPDATE proj_data_edition_summary
SET status = 'Sealed',
    content_hash = $2,
    publisher_facility_code = $3,
    publication_year = $4,
    license = COALESCE($5, license),
    dataset_ids = $6,
    sealed_at = $7,
    sealed_by = $8,
    updated_at = now()
WHERE edition_id = $1
"""

_PUBLISH_EDITION_SQL = """
UPDATE proj_data_edition_summary
SET status = 'Published',
    external_pid_scheme = $2,
    external_pid_value = $3,
    published_content_hash = $4,
    published_at = $5,
    published_by = $6,
    updated_at = now()
WHERE edition_id = $1
"""

_WITHDRAW_EDITION_SQL = """
UPDATE proj_data_edition_summary
SET status = 'Withdrawn',
    withdrawal_reason = $2,
    withdrawn_at = $3,
    withdrawn_by = $4,
    updated_at = now()
WHERE edition_id = $1
"""


class EditionSummaryProjection:
    """Maintains the `proj_data_edition_summary` read model."""

    name = "proj_data_edition_summary"
    subscribed_event_types = frozenset(
        {
            "EditionRegistered",
            "EditionDatasetAdded",
            "EditionDatasetRemoved",
            "EditionSealed",
            "EditionPublished",
            "EditionWithdrawn",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        payload = event.payload
        match event.event_type:
            case "EditionRegistered":
                edition_id = UUID(payload["edition_id"])
                dataset_uuids = [UUID(d) for d in payload["dataset_ids"]]
                creators_json = json.dumps(payload["creators"])
                await conn.execute(
                    _INSERT_EDITION_SQL,
                    edition_id,
                    payload["kind"],
                    payload["title"],
                    dataset_uuids,
                    creators_json,
                    payload.get("license"),
                    payload.get("publication_year"),
                    payload.get("publisher_facility_code"),
                    datetime.fromisoformat(payload["occurred_at"]),
                    UUID(payload["registered_by"]),
                )
            case "EditionDatasetAdded":
                edition_id = UUID(payload["edition_id"])
                dataset_id = UUID(payload["dataset_id"])
                await conn.execute(_ADD_DATASET_SQL, edition_id, dataset_id)
            case "EditionDatasetRemoved":
                edition_id = UUID(payload["edition_id"])
                dataset_id = UUID(payload["dataset_id"])
                await conn.execute(_REMOVE_DATASET_SQL, edition_id, dataset_id)
            case "EditionSealed":
                edition_id = UUID(payload["edition_id"])
                sealed_dataset_uuids = [UUID(d) for d in payload["sealed_dataset_ids"]]
                await conn.execute(
                    _SEAL_EDITION_SQL,
                    edition_id,
                    payload["content_hash"],
                    payload["publisher_facility_code"],
                    int(payload["publication_year"]),
                    payload.get("license"),
                    sealed_dataset_uuids,
                    datetime.fromisoformat(payload["occurred_at"]),
                    UUID(payload["sealed_by"]),
                )
            case "EditionPublished":
                edition_id = UUID(payload["edition_id"])
                await conn.execute(
                    _PUBLISH_EDITION_SQL,
                    edition_id,
                    payload["external_pid_scheme"],
                    payload["external_pid_value"],
                    payload["published_content_hash"],
                    datetime.fromisoformat(payload["occurred_at"]),
                    UUID(payload["published_by"]),
                )
            case "EditionWithdrawn":
                edition_id = UUID(payload["edition_id"])
                await conn.execute(
                    _WITHDRAW_EDITION_SQL,
                    edition_id,
                    payload["withdrawal_reason"],
                    datetime.fromisoformat(payload["occurred_at"]),
                    UUID(payload["withdrawn_by"]),
                )
            case _:
                pass


__all__ = ["EditionSummaryProjection"]
