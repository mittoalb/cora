"""Domain events emitted by the Family aggregate, plus the discriminated union.

## Phase 5i: rename + dual-match

Phase 5i (direct rename of Capability → Family per DLM-A
[[family-affordance-design-phases-5i-5j-lock]]):

- New event type names: `FamilyDefined`, `FamilyVersioned`,
  `FamilyDeprecated`, `FamilySettingsSchemaUpdated`.
- Dataclass field renamed `capability_id` → `family_id`.
- Payload key renamed `"capability_id"` → `"family_id"` for new events.
- `from_stored` dual-matches: BOTH legacy type strings
  (`"CapabilityDefined"`, etc.) AND new strings produce the new
  `Family*` dataclass instances. Legacy payloads still carry
  `"capability_id"` key; new payloads carry `"family_id"`.

Per Marten / Axon / Dudycz consensus on event-sourced rename:
old events stay in the log forever with original type names;
the read-time upcaster translates them to the new aggregate
shape. The dual-match arms stay forever (no later cleanup).

Status is NOT carried in event payloads — the event type itself
encodes the state change. The evolver hardcodes the mapping per
match arm.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class FamilyDefined:
    """A new device-class family was defined.

    Status is implicit (`Defined`) — the evolver sets it.
    """

    family_id: UUID
    name: str
    occurred_at: datetime


@dataclass(frozen=True)
class FamilyVersioned:
    """A family's definition was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`.
    `version_tag` is operator-supplied free text (1-50 chars).
    """

    family_id: UUID
    version_tag: str
    occurred_at: datetime


@dataclass(frozen=True)
class FamilyDeprecated:
    """A family was marked as no longer recommended for new Methods.

    Multi-source transition: `Defined | Versioned -> Deprecated`.
    Existing Methods that reference this Family are NOT automatically
    invalidated. Deprecation is advisory.
    """

    family_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class FamilySettingsSchemaUpdated:
    """The Family's `settings_schema` was set, replaced, or cleared.

    Phase 5g-a (originally CapabilitySettingsSchemaUpdated; renamed in
    5i). Carries the FULL replacement schema. Independent of the
    Defined/Versioned/Deprecated lifecycle: schema can be updated in
    any non-terminal state. The validator runs at decider time, so
    this event ALWAYS carries a valid schema or None.
    """

    family_id: UUID
    settings_schema: dict[str, Any] | None
    occurred_at: datetime


# Discriminated union of every event the Family aggregate emits.
FamilyEvent = FamilyDefined | FamilyVersioned | FamilyDeprecated | FamilySettingsSchemaUpdated


def event_type_name(event: FamilyEvent) -> str:
    """Discriminator string written into StoredEvent.event_type.

    New events emit `"FamilyDefined"` etc. Legacy `"CapabilityDefined"`
    events in the log are recognized by `from_stored` but never emitted
    again.
    """
    return type(event).__name__


def to_payload(event: FamilyEvent) -> dict[str, Any]:
    """Serialize a Family event to a JSON-friendly dict for jsonb storage.

    New events serialize with `"family_id"` key. Legacy events in the
    log already carry `"capability_id"` and are NOT rewritten.
    """
    match event:
        case FamilyDefined(family_id=family_id, name=name, occurred_at=occurred_at):
            return {
                "family_id": str(family_id),
                "name": name,
                "occurred_at": occurred_at.isoformat(),
            }
        case FamilyVersioned(
            family_id=family_id,
            version_tag=version_tag,
            occurred_at=occurred_at,
        ):
            return {
                "family_id": str(family_id),
                "version_tag": version_tag,
                "occurred_at": occurred_at.isoformat(),
            }
        case FamilyDeprecated(family_id=family_id, occurred_at=occurred_at):
            return {
                "family_id": str(family_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case FamilySettingsSchemaUpdated(
            family_id=family_id,
            settings_schema=settings_schema,
            occurred_at=occurred_at,
        ):
            return {
                "family_id": str(family_id),
                "settings_schema": settings_schema,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> FamilyEvent:
    """Rebuild a Family event from a StoredEvent loaded from the event store.

    Dual-matches both legacy `"Capability*"` event type strings (with
    `"capability_id"` payload key) and new `"Family*"` strings (with
    `"family_id"` key). Both produce the same `Family*` dataclass.
    Legacy arms stay forever per Marten/Axon canonical rename pattern.
    """
    payload = stored.payload
    match stored.event_type:
        # Legacy event type names from pre-5i. Payload key is
        # `"capability_id"`. Stays forever.
        case "CapabilityDefined":
            return FamilyDefined(
                family_id=UUID(payload["capability_id"]),
                name=payload["name"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "CapabilityVersioned":
            return FamilyVersioned(
                family_id=UUID(payload["capability_id"]),
                version_tag=payload["version_tag"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "CapabilityDeprecated":
            return FamilyDeprecated(
                family_id=UUID(payload["capability_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "CapabilitySettingsSchemaUpdated":
            return FamilySettingsSchemaUpdated(
                family_id=UUID(payload["capability_id"]),
                settings_schema=payload.get("settings_schema"),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        # New event type names from 5i onward. Payload key is `"family_id"`.
        case "FamilyDefined":
            return FamilyDefined(
                family_id=UUID(payload["family_id"]),
                name=payload["name"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "FamilyVersioned":
            return FamilyVersioned(
                family_id=UUID(payload["family_id"]),
                version_tag=payload["version_tag"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "FamilyDeprecated":
            return FamilyDeprecated(
                family_id=UUID(payload["family_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case "FamilySettingsSchemaUpdated":
            return FamilySettingsSchemaUpdated(
                family_id=UUID(payload["family_id"]),
                settings_schema=payload.get("settings_schema"),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown FamilyEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "FamilyDefined",
    "FamilyDeprecated",
    "FamilyEvent",
    "FamilySettingsSchemaUpdated",
    "FamilyVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
