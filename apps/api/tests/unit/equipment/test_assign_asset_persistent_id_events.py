"""Unit tests for AssetPersistentIdAssigned (de)serialization helpers.

Covers `to_payload` <-> `from_stored` round-trip for both supported
schemes (DOI + Handle) and the `Malformed*` wrap convention for
deserialization failures.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset.events import (
    AssetPersistentIdAssigned,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    """Build a StoredEvent shell; only event_type + payload are read by from_stored."""
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


def test_event_type_name_returns_asset_persistent_id_assigned_class_name() -> None:
    event = AssetPersistentIdAssigned(
        asset_id=uuid4(),
        persistent_id_scheme="DOI",
        persistent_id_value="10.5281/zenodo.1234567",
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "AssetPersistentIdAssigned"


def test_to_payload_serializes_asset_persistent_id_assigned_with_doi_scheme() -> None:
    asset_id = uuid4()
    event = AssetPersistentIdAssigned(
        asset_id=asset_id,
        persistent_id_scheme="DOI",
        persistent_id_value="10.5281/zenodo.1234567",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "persistent_id_scheme": "DOI",
        "persistent_id_value": "10.5281/zenodo.1234567",
        "occurred_at": _NOW.isoformat(),
    }


def test_to_payload_serializes_asset_persistent_id_assigned_with_handle_scheme() -> None:
    asset_id = uuid4()
    event = AssetPersistentIdAssigned(
        asset_id=asset_id,
        persistent_id_scheme="Handle",
        persistent_id_value="20.500.12613/12345",
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "asset_id": str(asset_id),
        "persistent_id_scheme": "Handle",
        "persistent_id_value": "20.500.12613/12345",
        "occurred_at": _NOW.isoformat(),
    }


def test_from_stored_rebuilds_asset_persistent_id_assigned_with_doi_scheme() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetPersistentIdAssigned",
        {
            "asset_id": str(asset_id),
            "persistent_id_scheme": "DOI",
            "persistent_id_value": "10.5281/zenodo.1234567",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetPersistentIdAssigned(
        asset_id=asset_id,
        persistent_id_scheme="DOI",
        persistent_id_value="10.5281/zenodo.1234567",
        occurred_at=_NOW,
    )


def test_from_stored_rebuilds_asset_persistent_id_assigned_with_handle_scheme() -> None:
    asset_id = uuid4()
    stored = _stored(
        "AssetPersistentIdAssigned",
        {
            "asset_id": str(asset_id),
            "persistent_id_scheme": "Handle",
            "persistent_id_value": "20.500.12613/12345",
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == AssetPersistentIdAssigned(
        asset_id=asset_id,
        persistent_id_scheme="Handle",
        persistent_id_value="20.500.12613/12345",
        occurred_at=_NOW,
    )


def test_asset_persistent_id_assigned_round_trips_through_to_payload_and_from_stored() -> None:
    original = AssetPersistentIdAssigned(
        asset_id=uuid4(),
        persistent_id_scheme="DOI",
        persistent_id_value="10.13139/OLCF/1234",
        occurred_at=_NOW,
    )
    stored = _stored("AssetPersistentIdAssigned", to_payload(original))
    assert from_stored(stored) == original


def test_asset_persistent_id_assigned_with_handle_scheme_round_trips() -> None:
    original = AssetPersistentIdAssigned(
        asset_id=uuid4(),
        persistent_id_scheme="Handle",
        persistent_id_value="20.500.12613/12345",
        occurred_at=_NOW,
    )
    stored = _stored("AssetPersistentIdAssigned", to_payload(original))
    assert from_stored(stored) == original


def test_asset_persistent_id_assigned_from_stored_with_unknown_scheme_raises_malformed() -> None:
    stored = _stored(
        "AssetPersistentIdAssigned",
        {
            "asset_id": str(uuid4()),
            "persistent_id_scheme": "ARK",
            "persistent_id_value": "ark:/12345/abc",
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed AssetPersistentIdAssigned payload"):
        from_stored(stored)


def test_asset_persistent_id_assigned_from_stored_with_missing_scheme_key_raises_malformed() -> (
    None
):
    stored = _stored(
        "AssetPersistentIdAssigned",
        {
            "asset_id": str(uuid4()),
            "persistent_id_value": "10.5281/zenodo.1234567",
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed AssetPersistentIdAssigned payload"):
        from_stored(stored)


def test_asset_persistent_id_assigned_from_stored_with_missing_value_key_raises_malformed() -> None:
    stored = _stored(
        "AssetPersistentIdAssigned",
        {
            "asset_id": str(uuid4()),
            "persistent_id_scheme": "DOI",
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed AssetPersistentIdAssigned payload"):
        from_stored(stored)


def test_asset_persistent_id_assigned_from_stored_with_empty_value_raises_malformed() -> None:
    stored = _stored(
        "AssetPersistentIdAssigned",
        {
            "asset_id": str(uuid4()),
            "persistent_id_scheme": "DOI",
            "persistent_id_value": "",
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed AssetPersistentIdAssigned payload"):
        from_stored(stored)


def test_asset_persistent_id_assigned_from_stored_with_whitespace_only_value_raises_malformed() -> (
    None
):
    stored = _stored(
        "AssetPersistentIdAssigned",
        {
            "asset_id": str(uuid4()),
            "persistent_id_scheme": "DOI",
            "persistent_id_value": "   ",
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed AssetPersistentIdAssigned payload"):
        from_stored(stored)


def test_asset_persistent_id_assigned_from_stored_with_malformed_asset_id_raises_malformed() -> (
    None
):
    stored = _stored(
        "AssetPersistentIdAssigned",
        {
            "asset_id": "not-a-uuid",
            "persistent_id_scheme": "DOI",
            "persistent_id_value": "10.5281/zenodo.1234567",
            "occurred_at": _NOW.isoformat(),
        },
    )
    with pytest.raises(ValueError, match="Malformed AssetPersistentIdAssigned payload"):
        from_stored(stored)
