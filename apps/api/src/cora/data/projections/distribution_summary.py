"""DistributionSummaryProjection: folds the Distribution aggregate's
genesis event and the Attestation aggregate's ChecksumVerified facts
into the ``proj_data_distribution_summary`` read model that backs
future list / get slices and downstream Verified/Stale-aware
consumers per [[project_data_distribution_design]] L27 +
[[project_data_attestation_design]] L7 / Slice C.

Subscribed events:
  - DistributionRegistered  -> INSERT (status='Registered', registered_at,
                                       registered_by, all 8 intrinsic /
                                       binding fields from genesis payload)
  - AttestationRecorded     -> UPDATE (kind=ChecksumVerified projection-only
                                       status flip: Match -> 'Verified',
                                       Mismatch -> 'Stale', Unreachable ->
                                       no-op, other kinds -> no-op).

The Verified / Stale flip per [[project_data_attestation_design]] Slice
C is projection-only (NO Distribution-stream event is emitted; the
Distribution stream stays genesis-only today). The Discarded
transition will ship in a future Distribution slice as an additive
event subscription here.

## ON CONFLICT semantics

Genesis INSERT uses ``ON CONFLICT (distribution_id) DO NOTHING`` for
stream-id idempotency (same precedent as DatasetSummaryProjection).

The partial UNIQUE INDEX on ``(dataset_id, supply_id, uri) WHERE
status != 'Discarded'`` may collide on a different distribution_id
when an operator races two register_distribution calls with the same
triple. Per [[project_data_distribution_design]] L31 (Supply
projection-writer precedent): catch ``asyncpg.exceptions.UniqueViolationError``,
log WARN with the colliding triple, allow the bookmark to advance.
Does NOT raise. The spine event was already emitted and the request
returned 201 before this writer ran; the dropped projection row is
eventual-consistency cleanup, NOT a user-facing error.

## Attestation UPDATE rowcount-zero policy

When an AttestationRecorded references a distribution_id that has no
matching row (Distribution projection lagging the Attestation
writer), the UPDATE returns rowcount=0. The writer logs a WARN with
``(attestation_id, distribution_id, intended_status)`` and continues;
the bookmark advances. The next projection tick recovers if the
Distribution writer catches up before the next Attestation. Per L20:
NO raise (raising would dead-letter the projection writer).
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

# Status flip from AttestationRecorded. The ``WHERE status != 'Discarded'``
# guard preserves the GDPR-shaped terminal: a Discarded Distribution
# does NOT flip back to Verified or Stale even if a stale verifier
# walks the URI after deletion.
_UPDATE_DISTRIBUTION_STATUS_SQL = """
UPDATE proj_data_distribution_summary
SET status = $1, updated_at = now()
WHERE distribution_id = $2 AND status != 'Discarded'
"""

#: Closed mapping from (kind, outcome) -> target Distribution.status
#: for the AttestationRecorded subscription. Only ChecksumVerified
#: flips status today; FormatValidated / ConformsToValidated /
#: BitRotChecked are absent (no flip). Unreachable is absent for
#: ChecksumVerified (transient; bytes' integrity unknown, not
#: refuted).
_ATTESTATION_STATUS_FLIPS: dict[tuple[str, str], str] = {
    ("ChecksumVerified", "Match"): "Verified",
    ("ChecksumVerified", "Mismatch"): "Stale",
}


class DistributionSummaryProjection:
    """Maintains the ``proj_data_distribution_summary`` read model."""

    name = "proj_data_distribution_summary"
    subscribed_event_types = frozenset({"DistributionRegistered", "AttestationRecorded"})

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        match event.event_type:
            case "DistributionRegistered":
                await self._apply_registered(event, conn)
            case "AttestationRecorded":
                await self._apply_attestation(event, conn)
            case _:
                pass

    async def _apply_registered(self, event: StoredEvent, conn: ConnectionLike) -> None:
        payload = event.payload
        distribution_id = UUID(payload["distribution_id"])
        dataset_id = UUID(payload["dataset_id"])
        supply_id = UUID(payload["supply_id"])
        uri = payload["uri"]
        # The event payload carries checksum + encoding as nested JSON
        # objects per L9. asyncpg's JSONB binding needs the value
        # pre-serialized to a string when the column is JSONB and the
        # value comes from a dict.
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
            # Partial UNIQUE INDEX collision on (dataset_id, supply_id,
            # uri) WHERE status != 'Discarded' per L31. The spine event
            # landed; the projection-side dropped row is eventual-
            # consistency cleanup. Mirrors Supply projection-writer
            # precedent.
            _log.warning(
                "distribution_summary.unique_violation_swallowed",
                distribution_id=str(distribution_id),
                dataset_id=str(dataset_id),
                supply_id=str(supply_id),
                uri=uri,
            )

    async def _apply_attestation(self, event: StoredEvent, conn: ConnectionLike) -> None:
        payload = event.payload
        raw_distribution = payload.get("distribution_id")
        if raw_distribution is None:
            # ConformsToValidated attestations do not bind a Distribution;
            # no status flip.
            return
        kind = payload["kind"]
        outcome = payload["outcome"]
        target_status = _ATTESTATION_STATUS_FLIPS.get((kind, outcome))
        if target_status is None:
            # Unreachable (transient) and non-ChecksumVerified kinds do
            # not flip status today.
            return
        distribution_id = UUID(raw_distribution)
        attestation_id = UUID(payload["attestation_id"])
        result = await conn.execute(
            _UPDATE_DISTRIBUTION_STATUS_SQL,
            target_status,
            distribution_id,
        )
        if _rowcount_zero(result):
            # Distribution projection writer hasn't materialized the
            # row yet (or the row was Discarded). Log and continue per
            # L20.
            _log.warning(
                "distribution_summary.attestation_update_skipped",
                attestation_id=str(attestation_id),
                distribution_id=str(distribution_id),
                intended_status=target_status,
            )


def _rowcount_zero(result: object) -> bool:
    """Inspect the asyncpg ``execute`` command tag for a zero rowcount.

    asyncpg returns a string like ``"UPDATE 0"`` or ``"UPDATE 1"`` from
    ``conn.execute`` (the count is the trailing integer). Treat any
    non-conforming tag conservatively as non-zero so we do NOT spam
    warnings on driver shape changes.
    """
    if not isinstance(result, str):
        return False
    parts = result.rsplit(" ", 1)
    if len(parts) != 2:
        return False
    try:
        return int(parts[1]) == 0
    except ValueError:
        return False


__all__ = ["DistributionSummaryProjection"]
