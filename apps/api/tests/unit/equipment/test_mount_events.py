"""Unit tests for Mount event serialization: to_payload / from_stored / wrap convention.

Coverage targets per the Frame test precedent:
  - Round-trip identity for all 5 events (genesis, decommission,
    placement update, install, uninstall).
  - Drawing optional round-trip (None + populated variants).
  - previously_installed_asset_id None vs populated variants.
  - Unknown event_type raises tagged ValueError.
  - Each from_stored arm wraps malformed payload into a
    'Malformed <EventName>' ValueError per
    project_from_stored_wrap_convention.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.mount import (
    MountAssetInstalled,
    MountAssetUninstalled,
    MountDecommissioned,
    MountPlacementUpdated,
    MountRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Mount",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _placement(parent_frame_id: object) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=259313.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent_frame_id,  # type: ignore[arg-type]
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


def _drawing() -> Drawing:
    return Drawing(system=DrawingSystem.ICMS, number="P4105090404-210000-00", revision="A")


@pytest.mark.unit
def test_event_type_name_returns_class_name_per_event_kind() -> None:
    frame_id = uuid4()
    assert (
        event_type_name(
            MountRegistered(
                mount_id=uuid4(),
                slot_code="x",
                parent_mount_id=None,
                placement=_placement(frame_id),
                drawing=None,
                occurred_at=_NOW,
            )
        )
        == "MountRegistered"
    )
    assert (
        event_type_name(MountDecommissioned(mount_id=uuid4(), reason="x", occurred_at=_NOW))
        == "MountDecommissioned"
    )
    assert (
        event_type_name(
            MountPlacementUpdated(
                mount_id=uuid4(),
                new_placement=_placement(frame_id),
                survey=None,
                occurred_at=_NOW,
            )
        )
        == "MountPlacementUpdated"
    )
    assert (
        event_type_name(
            MountAssetInstalled(
                mount_id=uuid4(),
                asset_id=uuid4(),
                previously_installed_asset_id=None,
                occurred_at=_NOW,
            )
        )
        == "MountAssetInstalled"
    )
    assert (
        event_type_name(
            MountAssetUninstalled(
                mount_id=uuid4(),
                asset_id=uuid4(),
                reason="x",
                occurred_at=_NOW,
            )
        )
        == "MountAssetUninstalled"
    )


@pytest.mark.unit
def test_mount_registered_round_trip_for_root_mount_without_drawing() -> None:
    mount_id = uuid4()
    frame_id = uuid4()
    event = MountRegistered(
        mount_id=mount_id,
        slot_code="02-BM-A-K-01",
        parent_mount_id=None,
        placement=_placement(frame_id),
        drawing=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["parent_mount_id"] is None
    assert payload["drawing"] is None
    rebuilt = from_stored(_stored("MountRegistered", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_mount_registered_round_trip_with_parent_and_drawing_preserves_all_fields() -> None:
    mount_id = uuid4()
    parent_mount = uuid4()
    frame_id = uuid4()
    drawing = _drawing()
    event = MountRegistered(
        mount_id=mount_id,
        slot_code="02-BM-A-K-01-CHILD",
        parent_mount_id=parent_mount,
        placement=_placement(frame_id),
        drawing=drawing,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("MountRegistered", payload))
    assert rebuilt == event
    assert isinstance(rebuilt, MountRegistered)
    assert rebuilt.drawing == drawing
    assert rebuilt.parent_mount_id == parent_mount


@pytest.mark.unit
def test_mount_decommissioned_round_trip_with_reason() -> None:
    mount_id = uuid4()
    event = MountDecommissioned(
        mount_id=mount_id,
        reason="slot removed during 2027 reconfiguration",
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("MountDecommissioned", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_placement_updated_round_trip_with_survey_payload() -> None:
    mount_id = uuid4()
    frame_id = uuid4()
    event = MountPlacementUpdated(
        mount_id=mount_id,
        new_placement=_placement(frame_id),
        survey={"instrument": "Leica AT960", "residual_mm": 0.18},
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("MountPlacementUpdated", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_placement_updated_round_trip_with_no_survey() -> None:
    """Additive-evolution: payload.get('survey') tolerates missing key."""
    mount_id = uuid4()
    frame_id = uuid4()
    event = MountPlacementUpdated(
        mount_id=mount_id,
        new_placement=_placement(frame_id),
        survey=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("MountPlacementUpdated", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_asset_installed_round_trip_first_install_has_no_prior() -> None:
    mount_id = uuid4()
    asset_id = uuid4()
    event = MountAssetInstalled(
        mount_id=mount_id,
        asset_id=asset_id,
        previously_installed_asset_id=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["previously_installed_asset_id"] is None
    rebuilt = from_stored(_stored("MountAssetInstalled", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_asset_installed_round_trip_swap_carries_prior_asset_id() -> None:
    mount_id = uuid4()
    prior = uuid4()
    new = uuid4()
    event = MountAssetInstalled(
        mount_id=mount_id,
        asset_id=new,
        previously_installed_asset_id=prior,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["previously_installed_asset_id"] == str(prior)
    rebuilt = from_stored(_stored("MountAssetInstalled", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_asset_uninstalled_round_trip_with_reason() -> None:
    mount_id = uuid4()
    asset_id = uuid4()
    event = MountAssetUninstalled(
        mount_id=mount_id,
        asset_id=asset_id,
        reason="removed for cleaning",
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("MountAssetUninstalled", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown MountEvent event_type"):
        from_stored(_stored("BogusMountEvent", {}))


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "MountRegistered",
        "MountDecommissioned",
        "MountPlacementUpdated",
        "MountAssetInstalled",
        "MountAssetUninstalled",
    ],
)
def test_from_stored_wraps_malformed_payload_into_tagged_value_error(event_type: str) -> None:
    """Per project_from_stored_wrap_convention: every arm wraps
    (KeyError, TypeError, AttributeError) into ValueError tagged
    with the event name."""
    with pytest.raises(ValueError, match=f"Malformed {event_type}"):
        from_stored(_stored(event_type, {}))


@pytest.mark.unit
def test_mount_registered_payload_includes_full_placement_and_drawing_structure() -> None:
    """The Placement and Drawing payload helpers must serialize every
    nested field; a typo would silently drop one."""
    mount_id = uuid4()
    parent_mount = uuid4()
    frame_id = uuid4()
    drawing = _drawing()
    event = MountRegistered(
        mount_id=mount_id,
        slot_code="02-BM-A-K-01",
        parent_mount_id=parent_mount,
        placement=_placement(frame_id),
        drawing=drawing,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    placement_payload = payload["placement"]
    drawing_payload = payload["drawing"]
    assert isinstance(placement_payload, dict)
    assert isinstance(drawing_payload, dict)
    placement_keys: set[str] = set(placement_payload.keys())  # pyright: ignore[reportUnknownArgumentType]
    drawing_keys: set[str] = set(drawing_payload.keys())  # pyright: ignore[reportUnknownArgumentType]
    assert placement_keys == {
        "x",
        "y",
        "z",
        "rx",
        "ry",
        "rz",
        "parent_frame_id",
        "reference_surface",
        "tol_x",
        "tol_y",
        "tol_z",
        "tol_rx",
        "tol_ry",
        "tol_rz",
        "units",
    }
    assert drawing_keys == {"system", "number", "revision"}
