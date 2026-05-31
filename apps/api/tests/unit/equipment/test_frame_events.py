"""Unit tests for Frame event serialization: to_payload / from_stored / wrap convention.

Mirrors the Asset events test file. Coverage targets:
  - Round-trip identity: from_stored(StoredEvent(to_payload(event))) == event.
  - Unknown event_type raises tagged ValueError.
  - Each from_stored arm wraps (KeyError, TypeError, AttributeError)
    into a "Malformed <EventName> payload" ValueError per
    `project_from_stored_wrap_convention`.
  - The Placement VO round-trips through _placement_to_payload /
    _placement_from_payload without field drift (15 fields, root-null
    variant).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.frame import (
    FrameDecommissioned,
    FramePlacementUpdated,
    FrameRegistered,
    FrameRevisionLink,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    """Minimal StoredEvent for from_stored tests (only event_type + payload read)."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Frame",
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


def _placement(parent: object) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=259313.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent,  # type: ignore[arg-type]
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


@pytest.mark.unit
def test_event_type_name_returns_class_name_per_event_kind() -> None:
    assert (
        event_type_name(
            FrameRegistered(
                frame_id=uuid4(),
                name="x",
                parent_frame_id=None,
                placement=None,
                occurred_at=_NOW,
            )
        )
        == "FrameRegistered"
    )
    parent = uuid4()
    assert (
        event_type_name(
            FramePlacementUpdated(
                frame_id=uuid4(),
                new_placement=_placement(parent),
                survey=None,
                occurred_at=_NOW,
            )
        )
        == "FramePlacementUpdated"
    )
    assert (
        event_type_name(FrameDecommissioned(frame_id=uuid4(), reason="x", occurred_at=_NOW))
        == "FrameDecommissioned"
    )


@pytest.mark.unit
def test_frame_registered_round_trip_for_root_frame() -> None:
    frame_id = uuid4()
    event = FrameRegistered(
        frame_id=frame_id,
        name="centerline_1p35_mrad",
        parent_frame_id=None,
        placement=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["frame_id"] == str(frame_id)
    assert payload["name"] == "centerline_1p35_mrad"
    assert payload["parent_frame_id"] is None
    assert payload["placement"] is None
    rebuilt = from_stored(_stored("FrameRegistered", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_frame_registered_round_trip_for_child_frame_preserves_placement_fields() -> None:
    frame_id = uuid4()
    parent = uuid4()
    placement = _placement(parent)
    event = FrameRegistered(
        frame_id=frame_id,
        name="centerline_5p1_mrad",
        parent_frame_id=parent,
        placement=placement,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("FrameRegistered", payload))
    assert rebuilt == event
    assert isinstance(rebuilt, FrameRegistered)
    assert rebuilt.placement == placement


@pytest.mark.unit
def test_frame_updated_round_trip_with_survey_payload() -> None:
    frame_id = uuid4()
    parent = uuid4()
    event = FramePlacementUpdated(
        frame_id=frame_id,
        new_placement=_placement(parent),
        survey={"instrument": "Leica AT960", "residual_mm": 0.18},
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("FramePlacementUpdated", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_frame_updated_round_trip_with_no_survey() -> None:
    """Additive-evolution: payload.get('survey') tolerates missing key."""
    frame_id = uuid4()
    parent = uuid4()
    event = FramePlacementUpdated(
        frame_id=frame_id,
        new_placement=_placement(parent),
        survey=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("FramePlacementUpdated", payload))
    assert rebuilt == event
    # Pre-survey-field legacy payloads (dropped survey key) still fold:
    legacy_payload = {k: v for k, v in payload.items() if k != "survey"}
    rebuilt_legacy = from_stored(_stored("FramePlacementUpdated", legacy_payload))
    assert rebuilt_legacy == event


@pytest.mark.unit
def test_frame_decommissioned_round_trip_with_reason() -> None:
    frame_id = uuid4()
    event = FrameDecommissioned(
        frame_id=frame_id,
        reason="superseded by recalibration 2026-05-30",
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    rebuilt = from_stored(_stored("FrameDecommissioned", payload))
    assert rebuilt == event


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="Unknown FrameEvent event_type"):
        from_stored(_stored("BogusFrameEvent", {}))


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    ["FrameRegistered", "FramePlacementUpdated", "FrameDecommissioned"],
)
def test_from_stored_wraps_malformed_payload_into_tagged_value_error(event_type: str) -> None:
    """Per project_from_stored_wrap_convention: every arm wraps
    (KeyError, TypeError, AttributeError) into ValueError tagged
    with the event name."""
    with pytest.raises(ValueError, match=f"Malformed {event_type}"):
        from_stored(_stored(event_type, {}))


@pytest.mark.unit
def test_from_stored_raises_on_malformed_uuid_in_frame_registered_payload() -> None:
    """A non-UUID string in frame_id triggers ValueError (UUID raises);
    the wrap-convention surfaces it through 'Malformed FrameRegistered'."""
    bad_payload: dict[str, object] = {
        "frame_id": "not-a-uuid",
        "name": "x",
        "parent_frame_id": None,
        "placement": None,
        "occurred_at": _NOW.isoformat(),
    }
    # UUID(non-uuid) raises ValueError directly. The wrap arm catches
    # KeyError/TypeError/AttributeError, NOT ValueError, so this leaks
    # out as a plain UUID ValueError. Pinned to document the gap.
    with pytest.raises(ValueError):
        from_stored(_stored("FrameRegistered", bad_payload))


@pytest.mark.unit
def test_frame_registered_round_trip_carries_supersedes_link() -> None:
    """Successor frames register with a FrameRevisionLink; both the
    predecessor pointer and the transform Placement must round-trip
    structurally."""
    frame_id = uuid4()
    predecessor = uuid4()
    link = FrameRevisionLink(
        predecessor_frame_id=predecessor,
        transform_from_predecessor=_placement(predecessor),
    )
    event = FrameRegistered(
        frame_id=frame_id,
        name="centerline_apsu",
        parent_frame_id=None,
        placement=None,
        occurred_at=_NOW,
        supersedes=link,
    )
    payload = to_payload(event)
    assert isinstance(payload["supersedes"], dict)
    assert payload["supersedes"]["predecessor_frame_id"] == str(predecessor)
    rebuilt = from_stored(_stored("FrameRegistered", payload))
    assert rebuilt == event
    assert isinstance(rebuilt, FrameRegistered)
    assert rebuilt.supersedes == link


@pytest.mark.unit
def test_frame_registered_round_trip_tolerates_legacy_payload_without_supersedes_key() -> None:
    """Additive evolution: pre-supersedes payloads (no `supersedes`
    key at all) deserialize to supersedes=None. Matches the
    `payload.get('survey')` pattern in FramePlacementUpdated."""
    frame_id = uuid4()
    legacy_payload: dict[str, object] = {
        "frame_id": str(frame_id),
        "name": "legacy_root_frame",
        "parent_frame_id": None,
        "placement": None,
        "occurred_at": _NOW.isoformat(),
        # NO supersedes key
    }
    rebuilt = from_stored(_stored("FrameRegistered", legacy_payload))
    assert isinstance(rebuilt, FrameRegistered)
    assert rebuilt.supersedes is None
    assert rebuilt.frame_id == frame_id


@pytest.mark.unit
def test_supersedes_payload_carries_predecessor_and_transform_fields() -> None:
    """The supersedes sub-payload must serialize both fields; a typo
    would silently drop one."""
    predecessor = uuid4()
    link = FrameRevisionLink(
        predecessor_frame_id=predecessor,
        transform_from_predecessor=_placement(predecessor),
    )
    event = FrameRegistered(
        frame_id=uuid4(),
        name="successor",
        parent_frame_id=None,
        placement=None,
        occurred_at=_NOW,
        supersedes=link,
    )
    payload = to_payload(event)
    supersedes_payload = payload["supersedes"]
    assert isinstance(supersedes_payload, dict)
    keys: set[str] = set(supersedes_payload.keys())  # pyright: ignore[reportUnknownArgumentType]
    assert keys == {"predecessor_frame_id", "transform_from_predecessor"}
    transform_payload = supersedes_payload["transform_from_predecessor"]  # pyright: ignore[reportUnknownVariableType]
    assert isinstance(transform_payload, dict)
    # Transform Placement must serialize all 15 fields just like any
    # other Placement payload; the same _placement_to_payload helper
    # is reused.
    assert len(transform_payload) == 15  # pyright: ignore[reportUnknownArgumentType]


@pytest.mark.unit
def test_placement_payload_carries_all_15_fields() -> None:
    """The Placement payload helper must serialize every field; a
    typo would silently drop one."""
    parent = uuid4()
    placement = _placement(parent)
    event = FramePlacementUpdated(
        frame_id=uuid4(),
        new_placement=placement,
        survey=None,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    placement_payload = payload["new_placement"]
    assert isinstance(placement_payload, dict)
    payload_keys: set[str] = set(placement_payload.keys())  # pyright: ignore[reportUnknownArgumentType]
    expected_keys = {
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
    assert payload_keys == expected_keys
