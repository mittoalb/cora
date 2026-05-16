"""Domain events emitted by the Method aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 6a shipped `MethodDefined`. Phase 6b adds `MethodVersioned`
and `MethodDeprecated` per the `Defined → Versioned → Deprecated`
lifecycle. MethodVersioned carries an operator-supplied
`version_tag` (free-text label like "v2" or "2026-Q3"; precedent:
AssetRelocated.reason and CapabilityVersioned). MethodDeprecated
carries no extra fields. Mirrors Capability's transition shape from
Equipment 5f-2.

## Payload conventions

`capabilities_needed` is stored as `list[UUID]` here (events carry
primitives per CONTRIBUTING.md; lists JSON-serialize cleanly). The
evolver converts to `frozenset` when folding into Method state. The
list is sorted by string form in `to_payload` so the same logical
capability set serializes deterministically — important for
hash-based idempotency and any future content-addressed lookup.
Same precedent as Trust's PolicyDefined.

Status is NOT carried in event payloads — the event type itself
encodes the state change (for example, `MethodVersioned ->
status=VERSIONED`). The evolver hardcodes the mapping per match
arm. Same precedent as `CapabilityDefined → DEFINED` /
`SubjectMounted → MOUNTED`.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class MethodDefined:
    """A new abstract technique-class recipe was defined.

    Status is implicit (`Defined`) — the evolver sets it.

    `capabilities_needed` carries the Capability ids the Method
    requires; eventual-consistency stance, no cross-aggregate
    verification.

    `supplies_needed` (post-10b, additive evolution) carries Supply
    KIND strings the Method requires — NOT Supply instance ids.
    Pre-10b events fold via `payload.get("supplies_needed", [])`. The
    list is sorted by string form in `to_payload` for persistence
    determinism (matches capabilities_needed). Default empty list.
    """

    method_id: UUID
    name: str
    capabilities_needed: list[UUID]
    occurred_at: datetime
    supplies_needed: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class MethodVersioned:
    """A method's definition was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`. The
    evolver sets status=VERSIONED and updates state.version to the
    new tag. The decider's source-state guard enforces that
    Deprecated methods can't be re-versioned.

    `version_tag` is operator-supplied free text (1-50 chars,
    validated at API boundary AND in the decider). Could be semver
    ("v2.1.0"), date-stamped ("2026-Q3"), or anything else
    institution-specific. Not a VO; same precedent as
    AssetRelocated.reason and CapabilityVersioned.
    """

    method_id: UUID
    version_tag: str
    occurred_at: datetime


@dataclass(frozen=True)
class MethodDeprecated:
    """A method was marked as no longer recommended for new Plans.

    Multi-source transition: `Defined | Versioned -> Deprecated`. The
    evolver sets status=DEPRECATED; `version` is preserved (the
    historical label of when the method was last revised before being
    deprecated remains visible).

    Existing Plans / Practices that reference this Method are NOT
    automatically invalidated. Deprecation is advisory at the BC
    layer; future Plan-side enrichment may surface a warning at
    bind-time when referencing a deprecated Method.
    """

    method_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class MethodParametersSchemaUpdated:
    """The Method's parameter-shape contract was updated (Phase 6g-a).

    `parameters_schema` is the new JSON Schema (Draft 2020-12,
    constrained subset) replacing whatever was on state. None clears
    the contract (Method declares no parameter shape; downstream Plans
    and Runs accept any dict). Schema-changes do NOT auto-revalidate
    pre-existing Plans / Runs; existing Plans preserve historical
    validity (locked, mirrors 5g-a posture).

    Validator (`parameters_validation.validate_parameters_schema`)
    runs at decide time so persisted payloads are always well-formed.
    Mirrors `CapabilitySettingsSchemaUpdated` shape from Equipment 5g-a.

    Status is NOT carried — schema updates are orthogonal to lifecycle
    (Defined / Versioned / Deprecated all permit schema updates).
    """

    method_id: UUID
    parameters_schema: dict[str, Any] | None
    occurred_at: datetime


# Discriminated union of every event the Method aggregate emits.
MethodEvent = MethodDefined | MethodVersioned | MethodDeprecated | MethodParametersSchemaUpdated


def event_type_name(event: MethodEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: MethodEvent) -> dict[str, Any]:
    """Serialize a Method event to a JSON-friendly dict for jsonb storage.

    `capabilities_needed` is sorted by UUID string form so the
    persisted payload is deterministic — same logical capability
    set, same payload bytes, same idempotency hash. Same precedent
    as Trust's PolicyDefined.
    """
    match event:
        case MethodDefined(
            method_id=method_id,
            name=name,
            capabilities_needed=capabilities_needed,
            supplies_needed=supplies_needed,
            occurred_at=occurred_at,
        ):
            return {
                "method_id": str(method_id),
                "name": name,
                "capabilities_needed": sorted(str(c) for c in capabilities_needed),
                # Phase 10b additive: kind strings sorted lexically for
                # deterministic payload bytes (matches capabilities_needed
                # convention; same idempotency-hash story).
                "supplies_needed": sorted(supplies_needed),
                "occurred_at": occurred_at.isoformat(),
            }
        case MethodVersioned(
            method_id=method_id,
            version_tag=version_tag,
            occurred_at=occurred_at,
        ):
            return {
                "method_id": str(method_id),
                "version_tag": version_tag,
                "occurred_at": occurred_at.isoformat(),
            }
        case MethodDeprecated(method_id=method_id, occurred_at=occurred_at):
            return {
                "method_id": str(method_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case MethodParametersSchemaUpdated(
            method_id=method_id,
            parameters_schema=parameters_schema,
            occurred_at=occurred_at,
        ):
            return {
                "method_id": str(method_id),
                "parameters_schema": parameters_schema,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> MethodEvent:
    """Rebuild a Method event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "MethodDefined":
            return MethodDefined(
                method_id=UUID(payload["method_id"]),
                name=payload["name"],
                capabilities_needed=[UUID(c) for c in payload["capabilities_needed"]],
                # Phase 10b forward-compat: pre-10b MethodDefined
                # payloads have no supplies_needed key; default to empty
                # list. Additive-evolution pattern.
                supplies_needed=list(payload.get("supplies_needed", [])),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "MethodVersioned":
            return MethodVersioned(
                method_id=UUID(payload["method_id"]),
                version_tag=payload["version_tag"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "MethodDeprecated":
            return MethodDeprecated(
                method_id=UUID(payload["method_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "MethodParametersSchemaUpdated":
            return MethodParametersSchemaUpdated(
                method_id=UUID(payload["method_id"]),
                parameters_schema=payload["parameters_schema"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown MethodEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "MethodDefined",
    "MethodDeprecated",
    "MethodEvent",
    "MethodParametersSchemaUpdated",
    "MethodVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
