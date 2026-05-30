"""Domain events emitted by the Credential aggregate, plus the discriminated union.

Five events shipped at BC genesis:

  - `CredentialRegistered`: genesis (status starts at Active).
  - `CredentialRotationStarted`: pending refs captured; status moves
    to Rotating.
  - `CredentialRotationCompleted`: pending promoted to current;
    status returns to Active.
  - `CredentialRotationAborted`: pending cleared; status returns to
    Active.
  - `CredentialRevoked`: terminal; status moves to Revoked.

Every event carries `occurred_at` plus a `<verb>_by_actor_id` denorm of
the envelope `principal_id` so projection consumers do not need to join
the envelope table for the most common per-event queries.

Per AH#6 of the locked design, neither the registration event nor the
rotation events carry raw secret bytes; only opaque pointers
(`secret_ref`, `public_material_ref`, `pending_secret_ref`,
`pending_public_material_ref`) cross the wire and land in jsonb. The
aggregate enforces this by typing those fields as `str`, not `bytes`;
events mirror that discipline.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.federation.aggregates.credential.state import CredentialPurpose
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class CredentialRegistered:
    """A new Credential was registered (genesis; status starts at Active).

    `secret_ref` and `public_material_ref` are opaque pointers handed
    off to the SecretStore adapter at use time. The aggregate does not
    resolve them at registration; deciders only check that
    `secret_ref` is non-empty after trimming.
    """

    credential_id: UUID
    facility_id: str
    audience: str
    purpose: CredentialPurpose
    secret_ref: str
    public_material_ref: str | None
    expires_at: datetime | None
    registered_by_actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class CredentialRotationStarted:
    """A rotation was started; pending material was captured.

    Moves the aggregate from `Active` to `Rotating`. The pending refs
    sit alongside the current refs until either
    `CredentialRotationCompleted` promotes them or
    `CredentialRotationAborted` discards them.
    """

    credential_id: UUID
    pending_secret_ref: str
    pending_public_material_ref: str | None
    rotation_started_by_actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class CredentialRotationCompleted:
    """A rotation completed; pending refs were promoted to current.

    Moves the aggregate from `Rotating` back to `Active`. The pending
    refs become the current refs; the prior current refs are
    discarded (Stage 2 deciders are responsible for telling the
    SecretStore adapter to revoke the prior material).
    """

    credential_id: UUID
    rotation_completed_by_actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class CredentialRotationAborted:
    """A rotation was aborted; pending refs were discarded.

    Moves the aggregate from `Rotating` back to `Active`. The pending
    refs are cleared. Used when a rotation cannot complete (peer
    refused new material, key generation failed in the SecretStore
    adapter, operator changed their mind).
    """

    credential_id: UUID
    rotation_aborted_by_actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class CredentialRevoked:
    """A credential was revoked (terminal).

    Valid from any non-revoked status (including past `expires_at`).
    No further transitions are accepted after this event.
    """

    credential_id: UUID
    revoked_by_actor_id: UUID
    occurred_at: datetime


CredentialEvent = (
    CredentialRegistered
    | CredentialRotationStarted
    | CredentialRotationCompleted
    | CredentialRotationAborted
    | CredentialRevoked
)


def event_type_name(event: CredentialEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: CredentialEvent) -> dict[str, Any]:
    """Serialise a Credential event to a JSON-friendly dict for jsonb storage."""
    match event:
        case CredentialRegistered(
            credential_id=credential_id,
            facility_id=facility_id,
            audience=audience,
            purpose=purpose,
            secret_ref=secret_ref,
            public_material_ref=public_material_ref,
            expires_at=expires_at,
            registered_by_actor_id=registered_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "credential_id": str(credential_id),
                "facility_id": facility_id,
                "audience": audience,
                "purpose": purpose.value,
                "secret_ref": secret_ref,
                "public_material_ref": public_material_ref,
                "expires_at": (expires_at.isoformat() if expires_at is not None else None),
                "registered_by_actor_id": str(registered_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case CredentialRotationStarted(
            credential_id=credential_id,
            pending_secret_ref=pending_secret_ref,
            pending_public_material_ref=pending_public_material_ref,
            rotation_started_by_actor_id=rotation_started_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "credential_id": str(credential_id),
                "pending_secret_ref": pending_secret_ref,
                "pending_public_material_ref": pending_public_material_ref,
                "rotation_started_by_actor_id": str(rotation_started_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case CredentialRotationCompleted(
            credential_id=credential_id,
            rotation_completed_by_actor_id=rotation_completed_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "credential_id": str(credential_id),
                "rotation_completed_by_actor_id": str(rotation_completed_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case CredentialRotationAborted(
            credential_id=credential_id,
            rotation_aborted_by_actor_id=rotation_aborted_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "credential_id": str(credential_id),
                "rotation_aborted_by_actor_id": str(rotation_aborted_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case CredentialRevoked(
            credential_id=credential_id,
            revoked_by_actor_id=revoked_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "credential_id": str(credential_id),
                "revoked_by_actor_id": str(revoked_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> CredentialEvent:
    """Rebuild a Credential event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "CredentialRegistered":
            try:
                raw_expires = payload.get("expires_at")
                return CredentialRegistered(
                    credential_id=UUID(payload["credential_id"]),
                    facility_id=payload["facility_id"],
                    audience=payload["audience"],
                    purpose=CredentialPurpose(payload["purpose"]),
                    secret_ref=payload["secret_ref"],
                    public_material_ref=payload.get("public_material_ref"),
                    expires_at=(
                        datetime.fromisoformat(raw_expires) if raw_expires is not None else None
                    ),
                    registered_by_actor_id=UUID(payload["registered_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed CredentialRegistered payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "CredentialRotationStarted":
            try:
                return CredentialRotationStarted(
                    credential_id=UUID(payload["credential_id"]),
                    pending_secret_ref=payload["pending_secret_ref"],
                    pending_public_material_ref=payload.get("pending_public_material_ref"),
                    rotation_started_by_actor_id=UUID(payload["rotation_started_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed CredentialRotationStarted payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "CredentialRotationCompleted":
            try:
                return CredentialRotationCompleted(
                    credential_id=UUID(payload["credential_id"]),
                    rotation_completed_by_actor_id=UUID(payload["rotation_completed_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed CredentialRotationCompleted payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "CredentialRotationAborted":
            try:
                return CredentialRotationAborted(
                    credential_id=UUID(payload["credential_id"]),
                    rotation_aborted_by_actor_id=UUID(payload["rotation_aborted_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed CredentialRotationAborted payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "CredentialRevoked":
            try:
                return CredentialRevoked(
                    credential_id=UUID(payload["credential_id"]),
                    revoked_by_actor_id=UUID(payload["revoked_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed CredentialRevoked payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case unknown:
            msg = f"Unknown Credential event type: {unknown!r}"
            raise ValueError(msg)


__all__ = [
    "CredentialEvent",
    "CredentialRegistered",
    "CredentialRevoked",
    "CredentialRotationAborted",
    "CredentialRotationCompleted",
    "CredentialRotationStarted",
    "event_type_name",
    "from_stored",
    "to_payload",
]
