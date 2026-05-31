"""Domain events emitted by the Seal aggregate, plus the discriminated union.

Five events shipped at BC genesis:

  - `SealInitialized`: genesis (singleton minted).
  - `SealPointerSigned`: a new head pointer was signed by the
    online key.
  - `SealOnlineKeyRotated`: the online key was swapped (the
    offline root authorizes this; the Stage-2 decider checks purpose
    binding and key separation).
  - `SealRepublishingStarted`: Live to Republishing.
  - `SealRepublishingCompleted`: Republishing to Live, with a
    fresh head hash and bumped sequence number.

The denorm `*_by_actor_id` field on each event mirrors the envelope's
`principal_id`; the brief locks this for Permit / Credential / Seal.
Per Path C
([[project_template_aggregate_timestamps]]) lifecycle bookkeeping
timestamps (`initialized_at`, `last_signed_at`) live on the projection,
not on aggregate state; `signed_at` is carried on the signing event
payload so the projection's `last_signed_at` reflects domain time
(mirrors Calibration revision `established_at`).

Wire shape is flat primitives: UUIDs render as strings, datetimes as
ISO-8601, SealStatus does not travel on payloads (the event
type IS the state-change indicator per the cross-aggregate convention).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class SealInitialized:
    """The Seal singleton was minted for this facility.

    Genesis event. Carries the initial online and offline key
    references; the decider has already verified key separation and
    purpose binding before commit. `initial_sequence_number` is 0;
    `initial_head_hash` is None (no pointer signed yet).
    """

    facility_id: str
    online_key_ref: UUID
    offline_key_ref: UUID
    initialized_by_actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class SealPointerSigned:
    """A new head pointer was signed by the online key.

    `head_hash` is the SHA-256 (lowercase hex) of the canonicalized
    head pointer body. `sequence_number` is strictly greater than the
    prior value (the decider rejects regressions via
    `SealSequenceNumberRegressionError`).

    `signed_at` is the wall-clock the signature was produced; carried
    explicitly so the projection's `last_signed_at` reflects domain
    time rather than event-envelope time (mirrors Calibration revision
    `established_at`).
    """

    facility_id: str
    head_hash: str
    sequence_number: int
    signed_at: datetime
    signed_by_actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class SealOnlineKeyRotated:
    """The online (warm) signing key was rotated to a fresh Credential.

    The Stage-2 decider has verified that the new `online_key_ref`
    differs from the existing `offline_key_ref` (key separation) and
    that the new credential's purpose is `SealOnlineSigning`. The
    offline root is unchanged by this event; rotating the offline
    root is a separate slice not in Stage 1 scope.

    `signed_by_offline_root` records the operator gesture that the
    offline root authorised this rotation (audit-only; verification of
    the offline signature itself is out of Stage-1 scope).
    """

    facility_id: str
    new_online_key_ref: UUID
    signed_by_offline_root: bool
    rotated_by_actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class SealRepublishingStarted:
    """The offline root began republishing the full registry tree.

    Status moves Live -> Republishing. The online key continues to
    sign pointers during the window; consumers may use the indicator
    to defer trust.
    """

    facility_id: str
    started_by_actor_id: UUID
    occurred_at: datetime
    reason: str | None = None


@dataclass(frozen=True)
class SealRepublishingCompleted:
    """The offline root finished republishing the registry tree.

    Status moves Republishing -> Live. `new_head_hash` is the SHA-256
    of the fresh head pointer; `new_sequence_number` is strictly
    greater than the prior value (the decider rejects regressions).
    """

    facility_id: str
    new_head_hash: str
    new_sequence_number: int
    completed_by_actor_id: UUID
    occurred_at: datetime


SealEvent = (
    SealInitialized
    | SealPointerSigned
    | SealOnlineKeyRotated
    | SealRepublishingStarted
    | SealRepublishingCompleted
)


def event_type_name(event: SealEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: SealEvent) -> dict[str, Any]:
    """Serialise a Seal event to a JSON-friendly dict for jsonb storage."""
    match event:
        case SealInitialized(
            facility_id=facility_id,
            online_key_ref=online_key_ref,
            offline_key_ref=offline_key_ref,
            initialized_by_actor_id=initialized_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "facility_id": facility_id,
                "online_key_ref": str(online_key_ref),
                "offline_key_ref": str(offline_key_ref),
                "initialized_by_actor_id": str(initialized_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case SealPointerSigned(
            facility_id=facility_id,
            head_hash=head_hash,
            sequence_number=sequence_number,
            signed_at=signed_at,
            signed_by_actor_id=signed_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "facility_id": facility_id,
                "head_hash": head_hash,
                "sequence_number": sequence_number,
                "signed_at": signed_at.isoformat(),
                "signed_by_actor_id": str(signed_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case SealOnlineKeyRotated(
            facility_id=facility_id,
            new_online_key_ref=new_online_key_ref,
            signed_by_offline_root=signed_by_offline_root,
            rotated_by_actor_id=rotated_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "facility_id": facility_id,
                "new_online_key_ref": str(new_online_key_ref),
                "signed_by_offline_root": signed_by_offline_root,
                "rotated_by_actor_id": str(rotated_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case SealRepublishingStarted(
            facility_id=facility_id,
            started_by_actor_id=started_by_actor_id,
            occurred_at=occurred_at,
            reason=reason,
        ):
            return {
                "facility_id": facility_id,
                "started_by_actor_id": str(started_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
                "reason": reason,
            }
        case SealRepublishingCompleted(
            facility_id=facility_id,
            new_head_hash=new_head_hash,
            new_sequence_number=new_sequence_number,
            completed_by_actor_id=completed_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "facility_id": facility_id,
                "new_head_hash": new_head_hash,
                "new_sequence_number": new_sequence_number,
                "completed_by_actor_id": str(completed_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover
            assert_never(event)


def from_stored(stored: StoredEvent) -> SealEvent:
    """Rebuild a Seal event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "SealInitialized":
            try:
                return SealInitialized(
                    facility_id=payload["facility_id"],
                    online_key_ref=UUID(payload["online_key_ref"]),
                    offline_key_ref=UUID(payload["offline_key_ref"]),
                    initialized_by_actor_id=UUID(payload["initialized_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed SealInitialized payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "SealPointerSigned":
            try:
                return SealPointerSigned(
                    facility_id=payload["facility_id"],
                    head_hash=payload["head_hash"],
                    sequence_number=payload["sequence_number"],
                    signed_at=datetime.fromisoformat(payload["signed_at"]),
                    signed_by_actor_id=UUID(payload["signed_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed SealPointerSigned payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "SealOnlineKeyRotated":
            try:
                return SealOnlineKeyRotated(
                    facility_id=payload["facility_id"],
                    new_online_key_ref=UUID(payload["new_online_key_ref"]),
                    signed_by_offline_root=payload["signed_by_offline_root"],
                    rotated_by_actor_id=UUID(payload["rotated_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed SealOnlineKeyRotated payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "SealRepublishingStarted":
            try:
                return SealRepublishingStarted(
                    facility_id=payload["facility_id"],
                    started_by_actor_id=UUID(payload["started_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    reason=payload.get("reason"),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed SealRepublishingStarted payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "SealRepublishingCompleted":
            try:
                return SealRepublishingCompleted(
                    facility_id=payload["facility_id"],
                    new_head_hash=payload["new_head_hash"],
                    new_sequence_number=payload["new_sequence_number"],
                    completed_by_actor_id=UUID(payload["completed_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed SealRepublishingCompleted payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case unknown:
            msg = f"Unknown Seal event type: {unknown!r}"
            raise ValueError(msg)


__all__ = [
    "SealEvent",
    "SealInitialized",
    "SealOnlineKeyRotated",
    "SealPointerSigned",
    "SealRepublishingCompleted",
    "SealRepublishingStarted",
    "event_type_name",
    "from_stored",
    "to_payload",
]
