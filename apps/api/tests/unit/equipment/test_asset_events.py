"""Unit tests for the Asset aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset.events import (
    AssetActivated,
    AssetCapabilityAdded,
    AssetCapabilityRemoved,
    AssetDecommissioned,
    AssetMaintenanceEntered,
    AssetRegistered,
    AssetRelocated,
    AssetRestoredFromMaintenance,
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
        stream_type="Asset",
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
    event = AssetRegistered(
        asset_id=uuid4(),
        name="APS-2BM",
        level="Site",
        parent_id=uuid4(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "AssetRegistered"


@pytest.mark.unit
def test_to_payload_serializes_asset_registered_with_parent() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    event = AssetRegistered(
        asset_id=asset_id,
        name="APS-2BM",
        level="Site",
        parent_id=parent_id,
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "name": "APS-2BM",
        "level": "Site",
        "parent_id": str(parent_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_asset_registered_with_null_parent() -> None:
    """Enterprise-level Assets have parent_id=None; the payload
    serializes it as JSON null. Pinned because the round-trip must
    handle Optional UUIDs cleanly."""
    asset_id = uuid4()
    event = AssetRegistered(
        asset_id=asset_id,
        name="ANL",
        level="Enterprise",
        parent_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["parent_id"] is None
    assert payload["level"] == "Enterprise"


@pytest.mark.unit
def test_from_stored_rebuilds_asset_registered_with_parent() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "APS-2BM",
            "level": "Site",
            "parent_id": str(parent_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetRegistered(
        asset_id=asset_id,
        name="APS-2BM",
        level="Site",
        parent_id=parent_id,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_from_stored_rebuilds_asset_registered_with_null_parent() -> None:
    """Enterprise root: payload's parent_id is JSON null → Python None."""
    asset_id = uuid4()
    stored = _stored(
        "AssetRegistered",
        {
            "asset_id": str(asset_id),
            "name": "ANL",
            "level": "Enterprise",
            "parent_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, AssetRegistered)
    assert rebuilt.parent_id is None
    assert rebuilt.level == "Enterprise"


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_with_parent() -> None:
    """Round-trip safety net for the typical (non-root) case."""
    original = AssetRegistered(
        asset_id=uuid4(),
        name="Eiger-2X-9M",
        level="Device",
        parent_id=uuid4(),
        occurred_at=_NOW,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_without_parent() -> None:
    """Round-trip safety net for Enterprise roots (parent_id=None)."""
    original = AssetRegistered(
        asset_id=uuid4(),
        name="ANL",
        level="Enterprise",
        parent_id=None,
        occurred_at=_NOW,
    )
    stored = _stored("AssetRegistered", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("CapabilityDefined", {})
    with pytest.raises(ValueError, match="Unknown AssetEvent event_type"):
        from_stored(stored)


# ---------- AssetActivated (Phase 5c) ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_activated_class_name() -> None:
    event = AssetActivated(asset_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetActivated"


@pytest.mark.unit
def test_to_payload_serializes_asset_activated_to_primitives() -> None:
    """Lifecycle NOT in payload — event TYPE encodes the state change.
    Pinned because adding a `lifecycle` field to the payload (e.g., to
    support a generic 'set lifecycle' command later) is an additive
    change that must be deliberate."""
    asset_id = uuid4()
    event = AssetActivated(asset_id=asset_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "lifecycle" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_asset_activated() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetActivated",
        {
            "asset_id": str(asset_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetActivated(asset_id=asset_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_activated() -> None:
    original = AssetActivated(asset_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetActivated", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetDecommissioned (Phase 5c) ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_decommissioned_class_name() -> None:
    event = AssetDecommissioned(asset_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetDecommissioned"


@pytest.mark.unit
def test_to_payload_serializes_asset_decommissioned_to_primitives() -> None:
    """Lifecycle NOT in payload — multi-source-to-single-target
    transitions still encode source state via the decider's guard, not
    the event payload (no `from_lifecycle` field). Same convention as
    Subject's SubjectRemoved (also multi-source-to-single-target)."""
    asset_id = uuid4()
    event = AssetDecommissioned(asset_id=asset_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "lifecycle" not in payload
    assert "from_lifecycle" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_asset_decommissioned() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetDecommissioned",
        {
            "asset_id": str(asset_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetDecommissioned(asset_id=asset_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_decommissioned() -> None:
    original = AssetDecommissioned(asset_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetDecommissioned", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetRelocated (Phase 5d) ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_relocated_class_name() -> None:
    event = AssetRelocated(
        asset_id=uuid4(),
        from_parent_id=uuid4(),
        to_parent_id=uuid4(),
        reason="site reorganization",
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "AssetRelocated"


@pytest.mark.unit
def test_to_payload_serializes_asset_relocated_with_both_parents_and_reason() -> None:
    """First event in the codebase whose payload carries source AND
    target state. Pinned because adding a `lifecycle` or other field
    is an additive change that must be deliberate, AND because both
    parent UUIDs must serialize as strings (not raw UUID instances)."""
    asset_id = uuid4()
    from_parent_id = uuid4()
    to_parent_id = uuid4()
    event = AssetRelocated(
        asset_id=asset_id,
        from_parent_id=from_parent_id,
        to_parent_id=to_parent_id,
        reason="moved from storage to BL2-IBP",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "from_parent_id": str(from_parent_id),
        "to_parent_id": str(to_parent_id),
        "reason": "moved from storage to BL2-IBP",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_asset_relocated() -> None:
    asset_id = uuid4()
    from_parent_id = uuid4()
    to_parent_id = uuid4()
    stored = _stored(
        "AssetRelocated",
        {
            "asset_id": str(asset_id),
            "from_parent_id": str(from_parent_id),
            "to_parent_id": str(to_parent_id),
            "reason": "site reorganization 2026-Q3",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetRelocated(
        asset_id=asset_id,
        from_parent_id=from_parent_id,
        to_parent_id=to_parent_id,
        reason="site reorganization 2026-Q3",
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_relocated() -> None:
    original = AssetRelocated(
        asset_id=uuid4(),
        from_parent_id=uuid4(),
        to_parent_id=uuid4(),
        reason="commissioning move",
        occurred_at=_NOW,
    )
    stored = _stored("AssetRelocated", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetMaintenanceEntered (Phase 5e) ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_maintenance_entered_class_name() -> None:
    event = AssetMaintenanceEntered(asset_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetMaintenanceEntered"


@pytest.mark.unit
def test_to_payload_serializes_asset_maintenance_entered_to_primitives() -> None:
    """Lifecycle NOT in payload — event TYPE encodes the state change.
    Same convention as AssetActivated / AssetDecommissioned."""
    asset_id = uuid4()
    event = AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "lifecycle" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_asset_maintenance_entered() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetMaintenanceEntered",
        {
            "asset_id": str(asset_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_maintenance_entered() -> None:
    original = AssetMaintenanceEntered(asset_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetMaintenanceEntered", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetRestoredFromMaintenance (Phase 5e) ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_restored_from_maintenance_class_name() -> None:
    event = AssetRestoredFromMaintenance(asset_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetRestoredFromMaintenance"


@pytest.mark.unit
def test_to_payload_serializes_asset_restored_from_maintenance_to_primitives() -> None:
    asset_id = uuid4()
    event = AssetRestoredFromMaintenance(asset_id=asset_id, occurred_at=_NOW)
    payload = to_payload(event)
    assert payload == {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert "lifecycle" not in payload


@pytest.mark.unit
def test_from_stored_rebuilds_asset_restored_from_maintenance() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetRestoredFromMaintenance",
        {
            "asset_id": str(asset_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetRestoredFromMaintenance(asset_id=asset_id, occurred_at=_NOW)


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_restored_from_maintenance() -> None:
    original = AssetRestoredFromMaintenance(asset_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetRestoredFromMaintenance", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetCapabilityAdded (Phase 5f-1) ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_capability_added_class_name() -> None:
    event = AssetCapabilityAdded(asset_id=uuid4(), capability_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetCapabilityAdded"


@pytest.mark.unit
def test_to_payload_serializes_asset_capability_added_to_primitives() -> None:
    asset_id = uuid4()
    capability_id = uuid4()
    event = AssetCapabilityAdded(asset_id=asset_id, capability_id=capability_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "capability_id": str(capability_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_asset_capability_added() -> None:
    asset_id = uuid4()
    capability_id = uuid4()
    stored = _stored(
        "AssetCapabilityAdded",
        {
            "asset_id": str(asset_id),
            "capability_id": str(capability_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetCapabilityAdded(
        asset_id=asset_id, capability_id=capability_id, occurred_at=_NOW
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_capability_added() -> None:
    original = AssetCapabilityAdded(asset_id=uuid4(), capability_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetCapabilityAdded", to_payload(original))
    assert from_stored(stored) == original


# ---------- AssetCapabilityRemoved (Phase 5f-1) ----------


@pytest.mark.unit
def test_event_type_name_returns_asset_capability_removed_class_name() -> None:
    event = AssetCapabilityRemoved(asset_id=uuid4(), capability_id=uuid4(), occurred_at=_NOW)
    assert event_type_name(event) == "AssetCapabilityRemoved"


@pytest.mark.unit
def test_to_payload_serializes_asset_capability_removed_to_primitives() -> None:
    asset_id = uuid4()
    capability_id = uuid4()
    event = AssetCapabilityRemoved(asset_id=asset_id, capability_id=capability_id, occurred_at=_NOW)
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "capability_id": str(capability_id),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_from_stored_rebuilds_asset_capability_removed() -> None:
    asset_id = uuid4()
    capability_id = uuid4()
    stored = _stored(
        "AssetCapabilityRemoved",
        {
            "asset_id": str(asset_id),
            "capability_id": str(capability_id),
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetCapabilityRemoved(
        asset_id=asset_id, capability_id=capability_id, occurred_at=_NOW
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips_for_asset_capability_removed() -> None:
    original = AssetCapabilityRemoved(asset_id=uuid4(), capability_id=uuid4(), occurred_at=_NOW)
    stored = _stored("AssetCapabilityRemoved", to_payload(original))
    assert from_stored(stored) == original
