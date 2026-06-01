"""SealSummaryProjection: folds the Seal aggregate's events into the
singleton-per-facility `proj_federation_seal_summary_summary` read model.

Subscribed events:
  - SealInitialized           -> INSERT (status='Live',
                                         current_sequence_number=0,
                                         initialized_at=occurred_at,
                                         last_signed_at=NULL)
  - SealPointerSigned         -> UPDATE current_head_hash,
                                        current_sequence_number,
                                        last_signed_by_actor_id,
                                        last_signed_at=signed_at
  - SealOnlineKeyRotated      -> UPDATE online_credential_id
  - SealRepublishingStarted   -> UPDATE status='Republishing'
  - SealRepublishingCompleted -> UPDATE status='Live',
                                        current_head_hash,
                                        current_sequence_number

## Singleton-per-facility

`facility_id` is the PRIMARY KEY; there is one row per facility. The
`SealInitialized` UPSERT uses ON CONFLICT DO NOTHING for idempotent
replay; subsequent transitions are pure UPDATE statements keyed on
`facility_id`.

## Path C lifecycle timestamps

`initialized_at` is filled from `SealInitialized.occurred_at`;
`last_signed_at` is filled from `SealPointerSigned.signed_at` so the
column reflects domain (signing) time rather than event-envelope time
(mirrors Calibration revision `established_at` precedent).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_SEAL_SQL = """
INSERT INTO proj_federation_seal_summary
    (facility_id, online_credential_id, offline_credential_id,
     current_head_hash, current_sequence_number,
     initialized_by_actor_id, last_signed_by_actor_id,
     status, initialized_at, last_signed_at)
VALUES ($1, $2, $3,
        NULL, 0,
        $4, NULL,
        'Live', $5, NULL)
ON CONFLICT (facility_id) DO NOTHING
"""

_UPDATE_POINTER_SIGNED_SQL = """
UPDATE proj_federation_seal_summary
SET current_head_hash = $2,
    current_sequence_number = $3,
    last_signed_by_actor_id = $4,
    last_signed_at = $5,
    updated_at = now()
WHERE facility_id = $1
"""

_UPDATE_ONLINE_KEY_ROTATED_SQL = """
UPDATE proj_federation_seal_summary
SET online_credential_id = $2,
    updated_at = now()
WHERE facility_id = $1
"""

_UPDATE_REPUBLISHING_STARTED_SQL = """
UPDATE proj_federation_seal_summary
SET status = 'Republishing',
    updated_at = now()
WHERE facility_id = $1
"""

_UPDATE_REPUBLISHING_COMPLETED_SQL = """
UPDATE proj_federation_seal_summary
SET status = 'Live',
    current_head_hash = $2,
    current_sequence_number = $3,
    updated_at = now()
WHERE facility_id = $1
"""


class SealSummaryProjection:
    """Maintains the `proj_federation_seal_summary` singleton-per-facility read model."""

    name = "proj_federation_seal_summary"
    subscribed_event_types = frozenset(
        {
            "SealInitialized",
            "SealPointerSigned",
            "SealOnlineKeyRotated",
            "SealRepublishingStarted",
            "SealRepublishingCompleted",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "SealInitialized":
            payload = event.payload
            initialized_at = datetime.fromisoformat(payload["occurred_at"])
            # SAVEPOINT-wrap: the keys_distinct CHECK and
            # singleton-per-facility UNIQUE are cross-stream invariants
            # that should not poison the bookmark transaction.
            async with conn.transaction():
                await conn.execute(
                    _INSERT_SEAL_SQL,
                    payload["facility_id"],
                    UUID(payload["online_credential_id"]),
                    UUID(payload["offline_credential_id"]),
                    UUID(payload["initialized_by_actor_id"]),
                    initialized_at,
                )
            return

        if event.event_type == "SealPointerSigned":
            payload = event.payload
            await conn.execute(
                _UPDATE_POINTER_SIGNED_SQL,
                payload["facility_id"],
                payload["head_hash"],
                payload["sequence_number"],
                UUID(payload["signed_by_actor_id"]),
                datetime.fromisoformat(payload["signed_at"]),
            )
            return

        if event.event_type == "SealOnlineKeyRotated":
            payload = event.payload
            await conn.execute(
                _UPDATE_ONLINE_KEY_ROTATED_SQL,
                payload["facility_id"],
                UUID(payload["new_online_credential_id"]),
            )
            return

        if event.event_type == "SealRepublishingStarted":
            payload = event.payload
            await conn.execute(
                _UPDATE_REPUBLISHING_STARTED_SQL,
                payload["facility_id"],
            )
            return

        if event.event_type == "SealRepublishingCompleted":
            payload = event.payload
            await conn.execute(
                _UPDATE_REPUBLISHING_COMPLETED_SQL,
                payload["facility_id"],
                payload["new_head_hash"],
                payload["new_sequence_number"],
            )
            return

        return


__all__ = ["SealSummaryProjection"]
