"""Unit tests for the Asset aggregate's event (de)serialization helpers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset.events import (
    AssetRegistered,
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
