"""CalibrationSummaryProjection: folds the Calibration aggregate's events
into the `proj_calibration_summary` read model that backs
`GET /calibrations` (list) + `GET /calibrations/{id}` (single).

Subscribed events:
  - CalibrationDefined           -> INSERT (revision_count=0,
                                            latest_revision_status=NULL,
                                            latest_revision_source_kind=NULL,
                                            last_revised_at=defined_at)
  - CalibrationRevisionAppended  -> UPDATE revision_count += 1,
                                           latest_revision_status,
                                           latest_revision_source_kind,
                                           last_revised_at

## Identity uniqueness enforced at the table layer

The `proj_calibration_summary_identity_unique` constraint on
`(target_id, quantity, operating_point)` is the
identity-tuple uniqueness anchor per the design memo Q6 lock.
Postgres jsonb provides value-based equality for free (key-order
normalization + numeric coercion `25 == 25.0` + duplicate-key dedup);
no RFC 8785 JCS needed.

Duplicate-identity inserts surface as IntegrityError at the projection
worker; the projection bookmark won't advance until the duplicate is
resolved (manual operator intervention OR the deferred lookup-port
pre-check from the design memo's watch items). For 12a-2 this is the
expected failure mode (the design memo defers the lookup-port pre-
check until pilot use shows duplicate incidents accumulate).

## Source-kind discriminator

`latest_revision_source_kind` is computed at projection write time
from the exclusive-arc `source_*_id` fields in the
`CalibrationRevisionAppended` payload (Q5 lock):

  source_procedure_id non-null  -> 'measured'
  source_dataset_id   non-null  -> 'computed'
  source_actor_id     non-null  -> 'asserted'

Exactly one is non-null (event-class invariant); the exclusive-arc
column shape mirrors `proj_calibration_revisions` (deferred to
12a-3+ if reconstruction pipelines need direct revision-level
queries).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_CALIBRATION_SQL = """
INSERT INTO proj_calibration_summary
    (calibration_id, target_id, quantity, operating_point,
     description, defined_at, last_revised_at, defined_by_actor_id,
     revision_count, latest_revision_status, latest_revision_source_kind)
VALUES ($1, $2, $3, $4::jsonb,
        $5, $6, $7, $8,
        0, NULL, NULL)
ON CONFLICT (calibration_id) DO NOTHING
"""

_UPDATE_REVISION_APPENDED_SQL = """
UPDATE proj_calibration_summary
SET revision_count = revision_count + 1,
    latest_revision_status = $2,
    latest_revision_source_kind = $3,
    last_revised_at = $4,
    updated_at = now()
WHERE calibration_id = $1
"""


def _source_kind_from_payload(payload: dict[str, Any]) -> str:
    """Compute the source-kind discriminator from exclusive-arc fields.

    Returns 'measured' / 'computed' / 'asserted' based on which of the
    three `source_*_id` fields is non-null (event-class invariant
    guarantees exactly one).
    """
    if payload.get("source_procedure_id") is not None:
        return "measured"
    if payload.get("source_dataset_id") is not None:
        return "computed"
    if payload.get("source_actor_id") is not None:
        return "asserted"
    # Defensive: the event class enforces exactly-one-non-null at
    # construction time; reaching here means a contaminated payload.
    return "unknown"


class CalibrationSummaryProjection:
    """Maintains the `proj_calibration_summary` read model."""

    name = "proj_calibration_summary"
    subscribed_event_types = frozenset(
        {
            "CalibrationDefined",
            "CalibrationRevisionAppended",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "CalibrationDefined":
            payload = event.payload
            # Wrap in SAVEPOINT so the identity-tuple UNIQUE violation
            # (cross-stream invariant) is recoverable at the worker
            # layer rather than poisoning the bookmark transaction.
            async with conn.transaction():
                # Path C: lifecycle timestamps come from envelope
                # `occurred_at`, not a redundant `defined_at` payload
                # field (which is now gone from CalibrationDefined).
                # `last_revised_at` seeds to the same value at
                # genesis and is bumped on each CalibrationRevisionAppended
                # to the revision's `established_at`.
                defined_at = datetime.fromisoformat(payload["occurred_at"])
                await conn.execute(
                    _INSERT_CALIBRATION_SQL,
                    UUID(payload["calibration_id"]),
                    UUID(payload["target_id"]),
                    payload["quantity"],
                    json.dumps(payload["operating_point"]),
                    payload.get("description"),
                    defined_at,
                    defined_at,
                    UUID(payload["defined_by_actor_id"]),
                )
            return

        if event.event_type == "CalibrationRevisionAppended":
            payload = event.payload
            await conn.execute(
                _UPDATE_REVISION_APPENDED_SQL,
                UUID(payload["calibration_id"]),
                payload["status"],
                _source_kind_from_payload(payload),
                datetime.fromisoformat(payload["established_at"]),
            )
            return

        # Unsubscribed event type (defensive).
        return


__all__ = ["CalibrationSummaryProjection"]
