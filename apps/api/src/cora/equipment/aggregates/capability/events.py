"""Domain events emitted by the Capability aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

Phase 5a shipped `CapabilityDefined`. Phase 5f-2 adds
`CapabilityVersioned` and `CapabilityDeprecated` per the
`Defined → Versioned → Deprecated` lifecycle. CapabilityVersioned
carries an operator-supplied `version_tag` (free-text label like
"v2" or "2026-Q3"); same precedent as `AssetRelocated.reason`.
CapabilityDeprecated carries no extra fields.

Status is NOT carried in event payloads — the event type itself
encodes the state change (for example, `CapabilityVersioned ->
status=VERSIONED`). The evolver hardcodes the mapping per match arm.
Same precedent as `SubjectMounted -> status=MOUNTED` /
`ActorDeactivated -> is_active=False`. See state.py docstring for
the rationale.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class CapabilityDefined:
    """A new technique-class capability was defined.

    Status is implicit (`Defined`) — the evolver sets it.
    """

    capability_id: UUID
    name: str
    occurred_at: datetime


@dataclass(frozen=True)
class CapabilityVersioned:
    """A capability's definition was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`. The
    evolver sets status=VERSIONED and updates state.current_version
    to the new tag. The decider's source-state guard enforces that
    Deprecated capabilities can't be re-versioned.

    `version_tag` is operator-supplied free text (1-50 chars,
    validated at API boundary AND in the decider). Could be semver
    ("v2.1.0"), date-stamped ("2026-Q3"), or anything else
    institution-specific. Not a VO; same precedent as
    AssetRelocated.reason.
    """

    capability_id: UUID
    version_tag: str
    occurred_at: datetime


@dataclass(frozen=True)
class CapabilityDeprecated:
    """A capability was marked as no longer recommended for new Methods.

    Multi-source transition: `Defined | Versioned -> Deprecated`. The
    evolver sets status=DEPRECATED; current_version is preserved
    (the historical label of when the capability was last revised
    before being deprecated remains visible).

    Existing Methods that reference this Capability are NOT
    automatically invalidated. Deprecation is advisory at the BC
    layer; future Method-side enrichment may surface a warning at
    define-time when referencing a deprecated Capability.
    """

    capability_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Capability aggregate emits.
CapabilityEvent = CapabilityDefined | CapabilityVersioned | CapabilityDeprecated


def event_type_name(event: CapabilityEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: CapabilityEvent) -> dict[str, Any]:
    """Serialize a Capability event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601 strings.
    """
    match event:
        case CapabilityDefined(capability_id=capability_id, name=name, occurred_at=occurred_at):
            return {
                "capability_id": str(capability_id),
                "name": name,
                "occurred_at": occurred_at.isoformat(),
            }
        case CapabilityVersioned(
            capability_id=capability_id,
            version_tag=version_tag,
            occurred_at=occurred_at,
        ):
            return {
                "capability_id": str(capability_id),
                "version_tag": version_tag,
                "occurred_at": occurred_at.isoformat(),
            }
        case CapabilityDeprecated(capability_id=capability_id, occurred_at=occurred_at):
            return {
                "capability_id": str(capability_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> CapabilityEvent:
    """Rebuild a Capability event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "CapabilityDefined":
            return CapabilityDefined(
                capability_id=UUID(payload["capability_id"]),
                name=payload["name"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "CapabilityVersioned":
            return CapabilityVersioned(
                capability_id=UUID(payload["capability_id"]),
                version_tag=payload["version_tag"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "CapabilityDeprecated":
            return CapabilityDeprecated(
                capability_id=UUID(payload["capability_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown CapabilityEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "CapabilityDefined",
    "CapabilityDeprecated",
    "CapabilityEvent",
    "CapabilityVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
