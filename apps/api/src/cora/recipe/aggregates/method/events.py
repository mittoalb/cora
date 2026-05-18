"""Domain events emitted by the Method aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 6a shipped `MethodDefined`. Phase 6b adds `MethodVersioned`
and `MethodDeprecated` per the `Defined → Versioned → Deprecated`
lifecycle. MethodVersioned carries an operator-supplied
`version_tag` (free-text label like "v2" or "2026-Q3"; precedent:
AssetRelocated.reason and FamilyVersioned). MethodDeprecated
carries no extra fields. Mirrors Family's transition shape from
Equipment 5f-2.

## Payload conventions

`needed_families` is stored as `list[UUID]` here (events carry
primitives per CONTRIBUTING.md; lists JSON-serialize cleanly). The
evolver converts to `frozenset` when folding into Method state. The
list is sorted by string form in `to_payload` so the same logical
family set serializes deterministically — important for
hash-based idempotency and any future content-addressed lookup.
Same precedent as Trust's PolicyDefined.

Status is NOT carried in event payloads — the event type itself
encodes the state change (for example, `MethodVersioned ->
status=VERSIONED`). The evolver hardcodes the mapping per match
arm. Same precedent as `FamilyDefined → DEFINED` /
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

    `needed_families` carries the Family ids the Method
    requires; eventual-consistency stance, no cross-aggregate
    verification.

    `needed_supplies` (post-10b, additive evolution) carries Supply
    KIND strings the Method requires — NOT Supply instance ids.
    Pre-10b events fold via `payload.get("needed_supplies", [])`. The
    list is sorted by string form in `to_payload` for persistence
    determinism (matches needed_families). Default empty list.
    """

    method_id: UUID
    name: str
    needed_families: list[UUID]
    occurred_at: datetime
    needed_supplies: list[str] = field(default_factory=list[str])
    # Phase 6l additive evolution: capability_id points to the
    # universal Capability template this Method realizes. Defaults
    # None for pre-6l events (additive-state pattern); post-6l decider
    # rejects None at define_method time per Pattern P.
    capability_id: UUID | None = None


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
    AssetRelocated.reason and FamilyVersioned.
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
    Mirrors `FamilySettingsSchemaUpdated` shape from Equipment 5g-a.

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

    `needed_families` is sorted by UUID string form so the
    persisted payload is deterministic — same logical family
    set, same payload bytes, same idempotency hash. Same precedent
    as Trust's PolicyDefined.
    """
    match event:
        case MethodDefined(
            method_id=method_id,
            name=name,
            needed_families=needed_families,
            needed_supplies=needed_supplies,
            capability_id=capability_id,
            occurred_at=occurred_at,
        ):
            return {
                "method_id": str(method_id),
                "name": name,
                "needed_families": sorted(str(c) for c in needed_families),
                # Phase 10b additive: kind strings sorted lexically for
                # deterministic payload bytes (matches needed_families
                # convention; same idempotency-hash story).
                "needed_supplies": sorted(needed_supplies),
                # Phase 6l additive: capability_id is None on pre-6l
                # events; the from_stored fallback to None preserves
                # legacy stream replay.
                "capability_id": (str(capability_id) if capability_id is not None else None),
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
            try:
                capability_raw = payload.get("capability_id")
                return MethodDefined(
                    method_id=UUID(payload["method_id"]),
                    name=payload["name"],
                    needed_families=[UUID(c) for c in payload["needed_families"]],
                    # Phase 10b forward-compat: pre-10b MethodDefined
                    # payloads have no needed_supplies key; default to empty
                    # list. Additive-evolution pattern.
                    needed_supplies=list(payload.get("needed_supplies", [])),
                    # Phase 6l forward-compat: pre-6l MethodDefined payloads
                    # have no capability_id key; default to None. Post-6l
                    # the decider enforces non-None at write time.
                    capability_id=(UUID(capability_raw) if capability_raw is not None else None),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed MethodDefined payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "MethodVersioned":
            try:
                return MethodVersioned(
                    method_id=UUID(payload["method_id"]),
                    version_tag=payload["version_tag"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed MethodVersioned payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "MethodDeprecated":
            try:
                return MethodDeprecated(
                    method_id=UUID(payload["method_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed MethodDeprecated payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "MethodParametersSchemaUpdated":
            try:
                return MethodParametersSchemaUpdated(
                    method_id=UUID(payload["method_id"]),
                    parameters_schema=payload["parameters_schema"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed MethodParametersSchemaUpdated payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
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
