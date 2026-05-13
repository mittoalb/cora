"""Unit tests for the Capability aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.capability.events import (
    CapabilityDefined,
    CapabilityDeprecated,
    CapabilitySchemaUpdated,
    CapabilityVersioned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    """Build a StoredEvent shell — only event_type + payload are read by from_stored."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Capability",
        stream_id=stream_id or uuid4(),  # type: ignore[arg-type]
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    event = CapabilityDefined(capability_id=uuid4(), name="Tomography", occurred_at=_NOW)
    assert event_type_name(event) == "CapabilityDefined"


@pytest.mark.unit
def test_to_payload_serializes_capability_defined_to_primitives() -> None:
    capability_id = uuid4()
    event = CapabilityDefined(capability_id=capability_id, name="Tomography", occurred_at=_NOW)
    assert to_payload(event) == {
        "capability_id": str(capability_id),
        "name": "Tomography",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_capability_defined() -> None:
    capability_id = uuid4()
    stored = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(capability_id),
            "name": "Tomography",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == CapabilityDefined(
        capability_id=capability_id, name="Tomography", occurred_at=_NOW
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    original = CapabilityDefined(capability_id=uuid4(), name="Tomography", occurred_at=_NOW)
    stored = _stored("CapabilityDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("ActorRegistered", {})
    with pytest.raises(ValueError, match="Unknown CapabilityEvent event_type"):
        from_stored(stored)


# ---------- CapabilityVersioned (Phase 5f-2) ----------


@pytest.mark.unit
def test_event_type_name_returns_capability_versioned_class_name() -> None:
    event = CapabilityVersioned(capability_id=uuid4(), version_tag="v2", occurred_at=_NOW)
    assert event_type_name(event) == "CapabilityVersioned"


@pytest.mark.unit
def test_to_payload_serializes_capability_versioned_with_version_tag() -> None:
    capability_id = uuid4()
    event = CapabilityVersioned(
        capability_id=capability_id, version_tag="2026-Q3", occurred_at=_NOW
    )
    assert to_payload(event) == {
        "capability_id": str(capability_id),
        "version_tag": "2026-Q3",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_capability_versioned() -> None:
    capability_id = uuid4()
    stored = _stored(
        "CapabilityVersioned",
        {
            "capability_id": str(capability_id),
            "version_tag": "v2",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == CapabilityVersioned(
        capability_id=capability_id, version_tag="v2", occurred_at=_NOW
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_capability_versioned() -> None:
    original = CapabilityVersioned(capability_id=uuid4(), version_tag="v3", occurred_at=_NOW)
    stored = _stored("CapabilityVersioned", to_payload(original))
    assert from_stored(stored) == original


# ---------- CapabilityDeprecated (Phase 5f-2) ----------


@pytest.mark.unit
def test_event_type_name_returns_capability_deprecated_class_name() -> None:
    event = CapabilityDeprecated(capability_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "CapabilityDeprecated"


@pytest.mark.unit
def test_to_payload_serializes_capability_deprecated_to_primitives() -> None:
    """Status NOT in payload — event TYPE encodes the state change.
    Pinned because adding a `status` field would be an additive change
    that must be deliberate."""
    capability_id = uuid4()
    event = CapabilityDeprecated(capability_id=capability_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "capability_id": str(capability_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "status" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_capability_deprecated() -> None:
    capability_id = uuid4()
    stored = _stored(
        "CapabilityDeprecated",
        {
            "capability_id": str(capability_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == CapabilityDeprecated(capability_id=capability_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_capability_deprecated() -> None:
    original = CapabilityDeprecated(capability_id=uuid4(), occurred_at=_NOW)
    stored = _stored("CapabilityDeprecated", to_payload(original))
    assert from_stored(stored) == original


# ---------- CapabilitySchemaUpdated (Phase 5g-a) ----------


_TEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"energy_kev": {"type": "number"}},
}


@pytest.mark.unit
def test_event_type_name_returns_capability_schema_updated_class_name() -> None:
    event = CapabilitySchemaUpdated(
        capability_id=uuid4(),
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "CapabilitySchemaUpdated"


@pytest.mark.unit
def test_to_payload_serializes_capability_schema_updated_with_schema() -> None:
    capability_id = uuid4()
    event = CapabilitySchemaUpdated(
        capability_id=capability_id,
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "capability_id": str(capability_id),
        "settings_schema": _TEST_SCHEMA,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_capability_schema_updated_with_none() -> None:
    """Clear-the-schema event payload carries explicit None."""
    capability_id = uuid4()
    event = CapabilitySchemaUpdated(
        capability_id=capability_id,
        settings_schema=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "capability_id": str(capability_id),
        "settings_schema": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_capability_schema_updated_with_schema() -> None:
    capability_id = uuid4()
    stored = _stored(
        "CapabilitySchemaUpdated",
        {
            "capability_id": str(capability_id),
            "settings_schema": _TEST_SCHEMA,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == CapabilitySchemaUpdated(
        capability_id=capability_id,
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_from_stored_rebuilds_capability_schema_updated_with_none_when_payload_missing_key() -> (
    None
):
    """Tolerates payloads missing the settings_schema key (treats as
    None). Matches the additive-evolution stance of from_stored."""
    capability_id = uuid4()
    stored = _stored(
        "CapabilitySchemaUpdated",
        {
            "capability_id": str(capability_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == CapabilitySchemaUpdated(
        capability_id=capability_id,
        settings_schema=None,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_capability_schema_updated() -> None:
    original = CapabilitySchemaUpdated(
        capability_id=uuid4(),
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )
    stored = _stored("CapabilitySchemaUpdated", to_payload(original))
    assert from_stored(stored) == original
