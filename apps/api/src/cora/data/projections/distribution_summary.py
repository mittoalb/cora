"""DistributionSummaryProjection: folds the Distribution aggregate's
genesis event into the `proj_data_distribution_summary` read model
that backs future list / get slices and the Attestation projection-
writer extension per [[project-data-distribution-design]] L27.

Subscribed events:
  - DistributionRegistered  -> INSERT (status='Registered', registered_at,
                                       registered_by, all 8 intrinsic /
                                       binding fields from genesis payload)

Ships subscribed only to DistributionRegistered today. The Verified /
Stale / Discarded transitions ship in follow-on slices; the Attestation
slice EXTENDS this writer to also subscribe to `AttestationRecorded`
and flip status per outcome (territory L7 projection-only flip).

## ON CONFLICT semantics

Genesis INSERT uses `ON CONFLICT (distribution_id) DO NOTHING` for
stream-id idempotency (same precedent as DatasetSummaryProjection).

The partial UNIQUE INDEX on `(dataset_id, supply_id, uri) WHERE
status != 'Discarded'` may collide on a different distribution_id
when an operator races two register_distribution calls with the same
triple. Per [[project-data-distribution-design]] L31 (Supply
projection-writer precedent): catch `asyncpg.exceptions.UniqueViolationError`,
log WARN with the colliding triple, allow the bookmark to advance.
Does NOT raise. The spine event was already emitted and the request
returned 201 before this writer ran; the dropped projection row is
eventual-consistency cleanup, NOT a user-facing error.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import datetime
from uuid import UUID

from asyncpg.exceptions import UniqueViolationError

from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_log = get_logger(__name__)

_INSERT_DISTRIBUTION_SQL = """
INSERT INTO proj_data_distribution_summary
    (distribution_id, dataset_id, supply_id, uri, checksum, byte_size,
     encoding, access_protocol, status, registered_at, registered_by)
VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7::jsonb, $8, 'Registered', $9, $10)
ON CONFLICT (distribution_id) DO NOTHING
"""


class DistributionSummaryProjection:
    """Maintains the `proj_data_distribution_summary` read model."""

    name = "proj_data_distribution_summary"
    subscribed_event_types = frozenset({"DistributionRegistered"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "DistributionRegistered":
                payload = event.payload
                distribution_id = UUID(payload["distribution_id"])
                dataset_id = UUID(payload["dataset_id"])
                supply_id = UUID(payload["supply_id"])
                uri = payload["uri"]
                # The event payload carries checksum + encoding as nested
                # JSON objects per L9. asyncpg's JSONB binding needs the
                # value pre-serialized to a string when the column is
                # JSONB and the value comes from a dict.
                checksum_json = json.dumps(payload["checksum"])
                encoding_json = json.dumps(payload["encoding"])
                try:
                    await conn.execute(
                        _INSERT_DISTRIBUTION_SQL,
                        distribution_id,
                        dataset_id,
                        supply_id,
                        uri,
                        checksum_json,
                        int(payload["byte_size"]),
                        encoding_json,
                        payload["access_protocol"],
                        datetime.fromisoformat(payload["occurred_at"]),
                        UUID(payload["registered_by"]),
                    )
                except UniqueViolationError:
                    # Partial UNIQUE INDEX collision on (dataset_id,
                    # supply_id, uri) WHERE status != 'Discarded' per L31.
                    # The spine event landed; the projection-side dropped
                    # row is eventual-consistency cleanup. Mirrors Supply
                    # projection-writer precedent.
                    _log.warning(
                        "distribution_summary.unique_violation_swallowed",
                        distribution_id=str(distribution_id),
                        dataset_id=str(dataset_id),
                        supply_id=str(supply_id),
                        uri=uri,
                    )
            case _:
                pass


__all__ = ["DistributionSummaryProjection"]
