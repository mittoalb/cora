"""CredentialSummaryProjection: folds the Credential aggregate's events
into the `proj_federation_credential_summary` read model that backs
the list / get slices shipped in Stage 2b/2c.

Subscribed events:
  - CredentialRegistered          -> INSERT (status='Active',
                                             registered_at=occurred_at)
  - CredentialRotationStarted     -> UPDATE status='Rotating',
                                            rotation_pending_*,
                                            rotation_started_at=occurred_at
  - CredentialRotationCompleted   -> UPDATE secret_ref + public_material_ref
                                            promoted from pending,
                                            clear rotation_pending_*,
                                            status='Active'
  - CredentialRotationAborted     -> UPDATE clear rotation_pending_*,
                                            clear rotation_started_at,
                                            status='Active'
  - CredentialRevoked             -> UPDATE status='Revoked',
                                            revoked_at=occurred_at

## Identity tuple

`(facility_id, audience, purpose)` is the identity tuple per the design
lock. The `proj_federation_credential_summary_identity_unique`
constraint enforces it at the table layer; duplicate-identity inserts
surface as IntegrityError at the projection worker.

## Secret material

The projection holds opaque refs only (`secret_ref`,
`public_material_ref`, `rotation_pending_*_ref`); never raw bytes. RLS
is FORCED on the table (per actor_profile precedent) as defense in
depth against owner-role bypass.

## RotationCompleted promotion

The aggregate's evolver promotes the prior `pending_*` refs to the
current `secret_ref` / `public_material_ref` slots when
`CredentialRotationCompleted` lands. The projection mirrors this
promotion in SQL via a self-referential UPDATE.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_CREDENTIAL_SQL = """
INSERT INTO proj_federation_credential_summary
    (credential_id, facility_id, audience, purpose,
     secret_ref, public_material_ref, expires_at,
     status, registered_at)
VALUES ($1, $2, $3, $4,
        $5, $6, $7,
        'Active', $8)
ON CONFLICT (credential_id) DO NOTHING
"""

_UPDATE_ROTATION_STARTED_SQL = """
UPDATE proj_federation_credential_summary
SET status = 'Rotating',
    rotation_pending_secret_ref = $2,
    rotation_pending_public_material_ref = $3,
    rotation_started_at = $4,
    updated_at = now()
WHERE credential_id = $1
"""

_UPDATE_ROTATION_COMPLETED_SQL = """
UPDATE proj_federation_credential_summary
SET secret_ref = COALESCE(rotation_pending_secret_ref, secret_ref),
    public_material_ref = rotation_pending_public_material_ref,
    rotation_pending_secret_ref = NULL,
    rotation_pending_public_material_ref = NULL,
    status = 'Active',
    updated_at = now()
WHERE credential_id = $1
"""

_UPDATE_ROTATION_ABORTED_SQL = """
UPDATE proj_federation_credential_summary
SET rotation_pending_secret_ref = NULL,
    rotation_pending_public_material_ref = NULL,
    rotation_started_at = NULL,
    status = 'Active',
    updated_at = now()
WHERE credential_id = $1
"""

_UPDATE_REVOKED_SQL = """
UPDATE proj_federation_credential_summary
SET status = 'Revoked',
    revoked_at = $2,
    updated_at = now()
WHERE credential_id = $1
"""


class CredentialSummaryProjection:
    """Maintains the `proj_federation_credential_summary` read model."""

    name = "proj_federation_credential_summary"
    subscribed_event_types = frozenset(
        {
            "CredentialRegistered",
            "CredentialRotationStarted",
            "CredentialRotationCompleted",
            "CredentialRotationAborted",
            "CredentialRevoked",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "CredentialRegistered":
            payload = event.payload
            raw_expires = payload.get("expires_at")
            expires_at = datetime.fromisoformat(raw_expires) if raw_expires is not None else None
            registered_at = datetime.fromisoformat(payload["occurred_at"])
            # SAVEPOINT-wrap: the identity-tuple UNIQUE
            # (facility_id, audience, purpose) is a cross-stream invariant
            # and may surface as IntegrityError on contaminated streams.
            async with conn.transaction():
                await conn.execute(
                    _INSERT_CREDENTIAL_SQL,
                    UUID(payload["credential_id"]),
                    payload["facility_id"],
                    payload["audience"],
                    payload["purpose"],
                    payload["secret_ref"],
                    payload.get("public_material_ref"),
                    expires_at,
                    registered_at,
                )
            return

        if event.event_type == "CredentialRotationStarted":
            payload = event.payload
            await conn.execute(
                _UPDATE_ROTATION_STARTED_SQL,
                UUID(payload["credential_id"]),
                payload["pending_secret_ref"],
                payload.get("pending_public_material_ref"),
                datetime.fromisoformat(payload["occurred_at"]),
            )
            return

        if event.event_type == "CredentialRotationCompleted":
            payload = event.payload
            await conn.execute(
                _UPDATE_ROTATION_COMPLETED_SQL,
                UUID(payload["credential_id"]),
            )
            return

        if event.event_type == "CredentialRotationAborted":
            payload = event.payload
            await conn.execute(
                _UPDATE_ROTATION_ABORTED_SQL,
                UUID(payload["credential_id"]),
            )
            return

        if event.event_type == "CredentialRevoked":
            payload = event.payload
            await conn.execute(
                _UPDATE_REVOKED_SQL,
                UUID(payload["credential_id"]),
                datetime.fromisoformat(payload["occurred_at"]),
            )
            return

        return


__all__ = ["CredentialSummaryProjection"]
