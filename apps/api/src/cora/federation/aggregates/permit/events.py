"""Domain events emitted by the Permit aggregate.

Five events span the 4-state FSM (shared across directions):

  - `PermitDefined`:   genesis (status = Defined); carries terms tagged-union
  - `PermitActivated`: Defined -> Active
  - `PermitSuspended`: Active -> Suspended
  - `PermitResumed`:   Suspended -> Active (audit twin of Activated)
  - `PermitRevoked`:   Defined | Active | Suspended -> Revoked (terminal)

Status is NOT carried in event payloads; the event type IS the
state-change indicator (matches `PermitActivated -> ACTIVE`,
`ClearanceSubmitted -> SUBMITTED`).

`terms` is serialized as a tagged dict with a `kind` discriminator
(`"Outbound" | "Inbound"`) so the polymorphic shape survives jsonb
round-trips. The decoder rebuilds the typed dataclass from the
discriminator; unknown discriminators raise tagged `ValueError`.

`scope_set` on OutboundTerms is serialized as a sorted list of
`[kind, name, qualifier]` triples for jsonb stability;
`allowed_credentials`, `allowed_payload_types`,
`allowed_artifact_kinds`, and the inbound-side
`inbound_allowed_artifact_kinds` frozenset fields ride through as
sorted string lists.

Each transition event carries an `<verb>_by_actor_id: UUID` denorm
of the envelope `principal_id` (matches CalibrationDefined /
ClearanceSubmitted precedent).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.federation.aggregates.permit.state import (
    AbiTier,
    Direction,
    InboundTerms,
    OnwardActionScope,
    OutboundTerms,
    ReadScope,
    ReceiptKind,
    ScopeRef,
)
from cora.infrastructure.ports.event_store import StoredEvent


def _serialize_scope_set(scope_set: frozenset[ScopeRef]) -> list[list[str | None]]:
    return sorted(
        ([s.kind, s.name, s.qualifier] for s in scope_set),
        key=lambda triple: (triple[0] or "", triple[1] or "", triple[2] or ""),
    )


def _deserialize_scope_set(raw: list[Any]) -> frozenset[ScopeRef]:
    return frozenset(
        ScopeRef(kind=triple[0], name=triple[1], qualifier=triple[2]) for triple in raw
    )


def serialize_terms(terms: OutboundTerms | InboundTerms) -> dict[str, Any]:
    match terms:
        case OutboundTerms(
            scope_set=scope_set,
            read_scope=read_scope,
            onward_action_scope=onward_action_scope,
        ):
            return {
                "kind": "Outbound",
                "scope_set": _serialize_scope_set(scope_set),
                "read_scope": read_scope.value,
                "onward_action_scope": onward_action_scope.value,
            }
        case InboundTerms(
            inbound_allowed_artifact_kinds=inbound_allowed_artifact_kinds,
            accepted_canonicalization_versions=accepted_canonicalization_versions,
            required_receipt_kinds=required_receipt_kinds,
            publisher_grant_correlation_handle=publisher_grant_correlation_handle,
        ):
            return {
                "kind": "Inbound",
                "inbound_allowed_artifact_kinds": sorted(inbound_allowed_artifact_kinds),
                "accepted_canonicalization_versions": sorted(accepted_canonicalization_versions),
                "required_receipt_kinds": sorted(r.value for r in required_receipt_kinds),
                "publisher_grant_correlation_handle": publisher_grant_correlation_handle,
            }
        case _:  # pragma: no cover
            assert_never(terms)


def deserialize_terms(raw: dict[str, Any]) -> OutboundTerms | InboundTerms:
    kind = raw.get("kind")
    match kind:
        case "Outbound":
            return OutboundTerms(
                scope_set=_deserialize_scope_set(raw["scope_set"]),
                read_scope=ReadScope(raw["read_scope"]),
                onward_action_scope=OnwardActionScope(raw["onward_action_scope"]),
            )
        case "Inbound":
            return InboundTerms(
                inbound_allowed_artifact_kinds=frozenset(raw["inbound_allowed_artifact_kinds"]),
                accepted_canonicalization_versions=frozenset(
                    raw["accepted_canonicalization_versions"]
                ),
                required_receipt_kinds=frozenset(
                    ReceiptKind(r) for r in raw["required_receipt_kinds"]
                ),
                publisher_grant_correlation_handle=raw.get("publisher_grant_correlation_handle"),
            )
        case unknown:
            msg = f"Unknown Permit terms kind discriminator: {unknown!r}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PermitDefined:
    permit_id: UUID
    peer_facility_id: str
    direction: Direction
    allowed_credentials: frozenset[UUID]
    allowed_payload_types: frozenset[str]
    allowed_artifact_kinds: frozenset[str]
    abi_tier_floor: AbiTier
    expires_at: datetime
    defined_by_actor_id: UUID
    terms: OutboundTerms | InboundTerms
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PermitActivated:
    permit_id: UUID
    activated_by_actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PermitSuspended:
    permit_id: UUID
    suspended_by_actor_id: UUID
    occurred_at: datetime
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PermitResumed:
    permit_id: UUID
    resumed_by_actor_id: UUID
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PermitRevoked:
    permit_id: UUID
    revoked_by_actor_id: UUID
    occurred_at: datetime
    reason: str | None = None


PermitEvent = PermitDefined | PermitActivated | PermitSuspended | PermitResumed | PermitRevoked


def event_type_name(event: PermitEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: PermitEvent) -> dict[str, Any]:
    match event:
        case PermitDefined(
            permit_id=permit_id,
            peer_facility_id=peer_facility_id,
            direction=direction,
            allowed_credentials=allowed_credentials,
            allowed_payload_types=allowed_payload_types,
            allowed_artifact_kinds=allowed_artifact_kinds,
            abi_tier_floor=abi_tier_floor,
            expires_at=expires_at,
            defined_by_actor_id=defined_by_actor_id,
            terms=terms,
            occurred_at=occurred_at,
        ):
            return {
                "permit_id": str(permit_id),
                "peer_facility_id": peer_facility_id,
                "direction": direction.value,
                "allowed_credentials": sorted(str(c) for c in allowed_credentials),
                "allowed_payload_types": sorted(allowed_payload_types),
                "allowed_artifact_kinds": sorted(allowed_artifact_kinds),
                "abi_tier_floor": abi_tier_floor.value,
                "expires_at": expires_at.isoformat(),
                "defined_by_actor_id": str(defined_by_actor_id),
                "terms": serialize_terms(terms),
                "occurred_at": occurred_at.isoformat(),
            }
        case PermitActivated(
            permit_id=permit_id,
            activated_by_actor_id=activated_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "permit_id": str(permit_id),
                "activated_by_actor_id": str(activated_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case PermitSuspended(
            permit_id=permit_id,
            suspended_by_actor_id=suspended_by_actor_id,
            occurred_at=occurred_at,
            reason=reason,
        ):
            return {
                "permit_id": str(permit_id),
                "suspended_by_actor_id": str(suspended_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
                "reason": reason,
            }
        case PermitResumed(
            permit_id=permit_id,
            resumed_by_actor_id=resumed_by_actor_id,
            occurred_at=occurred_at,
        ):
            return {
                "permit_id": str(permit_id),
                "resumed_by_actor_id": str(resumed_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case PermitRevoked(
            permit_id=permit_id,
            revoked_by_actor_id=revoked_by_actor_id,
            occurred_at=occurred_at,
            reason=reason,
        ):
            return {
                "permit_id": str(permit_id),
                "revoked_by_actor_id": str(revoked_by_actor_id),
                "occurred_at": occurred_at.isoformat(),
                "reason": reason,
            }
        case _:  # pragma: no cover
            assert_never(event)


def from_stored(stored: StoredEvent) -> PermitEvent:
    """Rebuild a Permit event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises tagged `ValueError` on
    unknown discriminators or malformed payloads so a contaminated
    stream fails loud rather than silently dropping events.
    """
    payload = stored.payload
    match stored.event_type:
        case "PermitDefined":
            try:
                return PermitDefined(
                    permit_id=UUID(payload["permit_id"]),
                    peer_facility_id=payload["peer_facility_id"],
                    direction=Direction(payload["direction"]),
                    allowed_credentials=frozenset(UUID(c) for c in payload["allowed_credentials"]),
                    allowed_payload_types=frozenset(payload["allowed_payload_types"]),
                    allowed_artifact_kinds=frozenset(payload["allowed_artifact_kinds"]),
                    abi_tier_floor=AbiTier(payload["abi_tier_floor"]),
                    expires_at=datetime.fromisoformat(payload["expires_at"]),
                    defined_by_actor_id=UUID(payload["defined_by_actor_id"]),
                    terms=deserialize_terms(payload["terms"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError, ValueError) as exc:
                msg = f"Malformed PermitDefined payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "PermitActivated":
            try:
                return PermitActivated(
                    permit_id=UUID(payload["permit_id"]),
                    activated_by_actor_id=UUID(payload["activated_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed PermitActivated payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "PermitSuspended":
            try:
                return PermitSuspended(
                    permit_id=UUID(payload["permit_id"]),
                    suspended_by_actor_id=UUID(payload["suspended_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    reason=payload.get("reason"),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed PermitSuspended payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "PermitResumed":
            try:
                return PermitResumed(
                    permit_id=UUID(payload["permit_id"]),
                    resumed_by_actor_id=UUID(payload["resumed_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed PermitResumed payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "PermitRevoked":
            try:
                return PermitRevoked(
                    permit_id=UUID(payload["permit_id"]),
                    revoked_by_actor_id=UUID(payload["revoked_by_actor_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    reason=payload.get("reason"),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed PermitRevoked payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case unknown:
            msg = f"Unknown Permit event type: {unknown!r}"
            raise ValueError(msg)


__all__ = [
    "PermitActivated",
    "PermitDefined",
    "PermitEvent",
    "PermitResumed",
    "PermitRevoked",
    "PermitSuspended",
    "deserialize_terms",
    "event_type_name",
    "from_stored",
    "serialize_terms",
    "to_payload",
]
