"""Unit tests for the Family aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.family.events import (
    FamilyDefined,
    FamilyDeprecated,
    FamilySettingsSchemaUpdated,
    FamilyVersioned,
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
        stream_type="Family",
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
    event = FamilyDefined(family_id=uuid4(), name="Tomography", occurred_at=_NOW)
    assert event_type_name(event) == "FamilyDefined"


@pytest.mark.unit
def test_to_payload_serializes_capability_defined_to_primitives() -> None:
    family_id = uuid4()
    event = FamilyDefined(family_id=family_id, name="Tomography", occurred_at=_NOW)
    assert to_payload(event) == {
        "family_id": str(family_id),
        "name": "Tomography",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_capability_defined() -> None:
    family_id = uuid4()
    stored = _stored(
        "FamilyDefined",
        {
            "family_id": str(family_id),
            "name": "Tomography",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilyDefined(family_id=family_id, name="Tomography", occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net: the (de)serialization pair must be each other's inverse."""
    original = FamilyDefined(family_id=uuid4(), name="Tomography", occurred_at=_NOW)
    stored = _stored("FamilyDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("ActorRegistered", {})
    with pytest.raises(ValueError, match="Unknown FamilyEvent event_type"):
        from_stored(stored)


# ---------- FamilyVersioned (Phase 5f-2) ----------


@pytest.mark.unit
def test_event_type_name_returns_capability_versioned_class_name() -> None:
    event = FamilyVersioned(family_id=uuid4(), version_tag="v2", occurred_at=_NOW)
    assert event_type_name(event) == "FamilyVersioned"


@pytest.mark.unit
def test_to_payload_serializes_capability_versioned_with_version_tag() -> None:
    family_id = uuid4()
    event = FamilyVersioned(family_id=family_id, version_tag="2026-Q3", occurred_at=_NOW)
    assert to_payload(event) == {
        "family_id": str(family_id),
        "version_tag": "2026-Q3",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_capability_versioned() -> None:
    family_id = uuid4()
    stored = _stored(
        "FamilyVersioned",
        {
            "family_id": str(family_id),
            "version_tag": "v2",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilyVersioned(family_id=family_id, version_tag="v2", occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_capability_versioned() -> None:
    original = FamilyVersioned(family_id=uuid4(), version_tag="v3", occurred_at=_NOW)
    stored = _stored("FamilyVersioned", to_payload(original))
    assert from_stored(stored) == original


# ---------- FamilyDeprecated (Phase 5f-2) ----------


@pytest.mark.unit
def test_event_type_name_returns_capability_deprecated_class_name() -> None:
    event = FamilyDeprecated(family_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "FamilyDeprecated"


@pytest.mark.unit
def test_to_payload_serializes_capability_deprecated_to_primitives() -> None:
    """Status NOT in payload — event TYPE encodes the state change.
    Pinned because adding a `status` field would be an additive change
    that must be deliberate."""
    family_id = uuid4()
    event = FamilyDeprecated(family_id=family_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "family_id": str(family_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "status" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_capability_deprecated() -> None:
    family_id = uuid4()
    stored = _stored(
        "FamilyDeprecated",
        {
            "family_id": str(family_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilyDeprecated(family_id=family_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_capability_deprecated() -> None:
    original = FamilyDeprecated(family_id=uuid4(), occurred_at=_NOW)
    stored = _stored("FamilyDeprecated", to_payload(original))
    assert from_stored(stored) == original


# ---------- FamilySettingsSchemaUpdated (Phase 5g-a) ----------


_TEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
}


@pytest.mark.unit
def test_event_type_name_returns_capability_settings_schema_updated_class_name() -> None:
    event = FamilySettingsSchemaUpdated(
        family_id=uuid4(),
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "FamilySettingsSchemaUpdated"


@pytest.mark.unit
def test_to_payload_serializes_capability_settings_schema_updated_with_schema() -> None:
    family_id = uuid4()
    event = FamilySettingsSchemaUpdated(
        family_id=family_id,
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "family_id": str(family_id),
        "settings_schema": _TEST_SCHEMA,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_capability_settings_schema_updated_with_none() -> None:
    """Clear-the-schema event payload carries explicit None."""
    family_id = uuid4()
    event = FamilySettingsSchemaUpdated(
        family_id=family_id,
        settings_schema=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "family_id": str(family_id),
        "settings_schema": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_capability_settings_schema_updated_with_schema() -> None:
    family_id = uuid4()
    stored = _stored(
        "FamilySettingsSchemaUpdated",
        {
            "family_id": str(family_id),
            "settings_schema": _TEST_SCHEMA,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilySettingsSchemaUpdated(
        family_id=family_id,
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_from_stored_rebuilds_settings_schema_updated_with_none_when_payload_missing() -> None:
    """Tolerates payloads missing the settings_schema key (treats as
    None). Matches the additive-evolution stance of from_stored."""
    family_id = uuid4()
    stored = _stored(
        "FamilySettingsSchemaUpdated",
        {
            "family_id": str(family_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilySettingsSchemaUpdated(
        family_id=family_id,
        settings_schema=None,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_capability_settings_schema_updated() -> None:
    original = FamilySettingsSchemaUpdated(
        family_id=uuid4(),
        settings_schema=_TEST_SCHEMA,
        occurred_at=_NOW,
    )
    stored = _stored("FamilySettingsSchemaUpdated", to_payload(original))
    assert from_stored(stored) == original


# ---------- Phase 5i dual-match: legacy "Capability*" event types ----------
#
# Per DLM-A direct-rename pattern (Marten/Axon canonical): old event
# type strings stay in the log forever; from_stored upcasts them to
# the new Family* dataclasses. These tests pin the dual-match arms so
# a future refactor can't silently break replay safety.


@pytest.mark.unit
def test_from_stored_upcasts_legacy_capability_defined_to_family_defined() -> None:
    """Pre-5i events have event_type='CapabilityDefined' and payload key
    'capability_id'. from_stored must produce a FamilyDefined with the
    new .family_id field populated from the legacy key."""
    legacy_id = uuid4()
    stored = _stored(
        "CapabilityDefined",
        {
            "capability_id": str(legacy_id),
            "name": "LegacyRotaryStage",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilyDefined(family_id=legacy_id, name="LegacyRotaryStage", occurred_at=_NOW)


@pytest.mark.unit
def test_from_stored_upcasts_legacy_capability_versioned_to_family_versioned() -> None:
    legacy_id = uuid4()
    stored = _stored(
        "CapabilityVersioned",
        {
            "capability_id": str(legacy_id),
            "version_tag": "v3",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilyVersioned(family_id=legacy_id, version_tag="v3", occurred_at=_NOW)


@pytest.mark.unit
def test_from_stored_upcasts_legacy_capability_deprecated_to_family_deprecated() -> None:
    legacy_id = uuid4()
    stored = _stored(
        "CapabilityDeprecated",
        {
            "capability_id": str(legacy_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilyDeprecated(family_id=legacy_id, occurred_at=_NOW)


@pytest.mark.unit
def test_from_stored_upcasts_legacy_capability_settings_schema_updated() -> None:
    legacy_id = uuid4()
    stored = _stored(
        "CapabilitySettingsSchemaUpdated",
        {
            "capability_id": str(legacy_id),
            "settings_schema": _TEST_SCHEMA,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilySettingsSchemaUpdated(
        family_id=legacy_id, settings_schema=_TEST_SCHEMA, occurred_at=_NOW
    )


@pytest.mark.unit
def test_from_stored_upcasts_legacy_settings_schema_updated_with_null_schema() -> None:
    """Pre-5i CapabilitySettingsSchemaUpdated could carry settings_schema=null
    (operator explicitly cleared the schema). The upcast must preserve that
    None rather than confuse it with an unset field."""
    legacy_id = uuid4()
    stored = _stored(
        "CapabilitySettingsSchemaUpdated",
        {
            "capability_id": str(legacy_id),
            "settings_schema": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == FamilySettingsSchemaUpdated(
        family_id=legacy_id, settings_schema=None, occurred_at=_NOW
    )
