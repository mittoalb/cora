"""Unit tests for the Placement value object + ReferenceSurface + UnitSystem enums."""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from cora.equipment.aggregates._placement import (
    InvalidPlacementError,
    Placement,
    ReferenceSurface,
    UnitSystem,
)


def _make_placement(**overrides: object) -> Placement:
    defaults: dict[str, object] = {
        "x": 0.0,
        "y": 0.0,
        "z": 259313.0,
        "rx": 0.0,
        "ry": 0.0,
        "rz": 0.0,
        "parent_frame": uuid4(),
        "reference_surface": ReferenceSurface.SHIELDING_FACE,
        "tol_x": 0.25,
        "tol_y": 0.25,
        "tol_z": 5.0,
        "tol_rx": 0.0,
        "tol_ry": 0.0,
        "tol_rz": 0.0,
        "units": UnitSystem.SI_MM_RAD,
    }
    defaults.update(overrides)
    return Placement(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
def test_reference_surface_values_are_pascalcase_strings() -> None:
    """Pinned: ReferenceSurface serializes as 'ThermalFace' / 'OpticCenter' /
    'ShieldingFace' so the JSON wire format reads naturally and matches
    enum precedent (PortDirection)."""
    assert ReferenceSurface.THERMAL_FACE.value == "ThermalFace"
    assert ReferenceSurface.OPTIC_CENTER.value == "OpticCenter"
    assert ReferenceSurface.SHIELDING_FACE.value == "ShieldingFace"


@pytest.mark.unit
def test_reference_surface_is_closed_three_value_enum() -> None:
    """The v1 enum is closed at three values; adding a fourth is a
    deliberate cross-facility decision per the design memo."""
    assert {member.name for member in ReferenceSurface} == {
        "THERMAL_FACE",
        "OPTIC_CENTER",
        "SHIELDING_FACE",
    }


@pytest.mark.unit
def test_unit_system_v1_is_single_value_si_mm_rad_only() -> None:
    """v1 has one UnitSystem (`SI_mm_rad`); new values require an
    explicit non-SI deployment trigger."""
    assert UnitSystem.SI_MM_RAD.value == "SI_mm_rad"
    assert {member.name for member in UnitSystem} == {"SI_MM_RAD"}


@pytest.mark.unit
def test_placement_constructs_with_valid_inputs() -> None:
    parent = uuid4()
    p = Placement(
        x=1.0,
        y=2.0,
        z=3.0,
        rx=0.1,
        ry=0.2,
        rz=0.3,
        parent_frame=parent,
        reference_surface=ReferenceSurface.OPTIC_CENTER,
        tol_x=0.5,
        tol_y=0.5,
        tol_z=1.0,
        tol_rx=0.01,
        tol_ry=0.01,
        tol_rz=0.01,
        units=UnitSystem.SI_MM_RAD,
    )
    assert p.x == 1.0
    assert p.parent_frame == parent
    assert p.reference_surface is ReferenceSurface.OPTIC_CENTER
    assert p.units is UnitSystem.SI_MM_RAD


@pytest.mark.unit
def test_placement_accepts_zero_tolerances() -> None:
    """Zero tolerance is meaningful ('exact'); only negative is rejected."""
    p = _make_placement(tol_x=0.0, tol_y=0.0, tol_z=0.0)
    assert p.tol_x == 0.0


@pytest.mark.unit
@pytest.mark.parametrize(
    "field",
    ["tol_x", "tol_y", "tol_z", "tol_rx", "tol_ry", "tol_rz"],
)
def test_placement_rejects_negative_tolerance(field: str) -> None:
    """Every tolerance field is independently checked; negative on any
    axis raises with the field name in the reason."""
    with pytest.raises(InvalidPlacementError) as info:
        _make_placement(**{field: -0.1})
    assert field in info.value.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "field",
    ["x", "y", "z", "rx", "ry", "rz", "tol_x", "tol_y", "tol_z", "tol_rx", "tol_ry", "tol_rz"],
)
def test_placement_rejects_nan_on_any_numeric_field(field: str) -> None:
    """NaN must be caught at the VO. An unguarded NaN breaks the
    update_placement no-op-on-equal idempotency (NaN != NaN) and
    serializes as a JSON literal that asyncpg's jsonb codec rejects
    at write time as a 500."""
    with pytest.raises(InvalidPlacementError) as info:
        _make_placement(**{field: float("nan")})
    assert field in info.value.reason
    assert "finite" in info.value.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "field",
    ["x", "y", "z", "rx", "ry", "rz", "tol_x", "tol_y", "tol_z", "tol_rx", "tol_ry", "tol_rz"],
)
def test_placement_rejects_positive_infinity_on_any_numeric_field(field: str) -> None:
    with pytest.raises(InvalidPlacementError) as info:
        _make_placement(**{field: float("inf")})
    assert field in info.value.reason
    assert "finite" in info.value.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "field",
    ["x", "y", "z", "rx", "ry", "rz"],
)
def test_placement_rejects_negative_infinity_on_position_field(field: str) -> None:
    """Negative infinity hits the finiteness check before the
    tolerance non-negativity check; the error message names the
    position field, not 'must be non-negative'."""
    with pytest.raises(InvalidPlacementError) as info:
        _make_placement(**{field: float("-inf")})
    assert field in info.value.reason
    assert "finite" in info.value.reason


@pytest.mark.unit
def test_invalid_placement_error_carries_reason() -> None:
    """`reason` surfaces in the route's 400 body; pin the attribute."""
    err = InvalidPlacementError("tol_x must be non-negative (got: -1.0)")
    assert err.reason == "tol_x must be non-negative (got: -1.0)"
    assert "tol_x" in str(err)


@pytest.mark.unit
def test_placement_is_frozen() -> None:
    p = _make_placement()
    with pytest.raises(FrozenInstanceError):
        p.x = 99.0  # type: ignore[misc]


@pytest.mark.unit
def test_placement_equality_is_structural() -> None:
    """Two Placements with identical fields are equal regardless of
    construction order."""
    parent = uuid4()
    a = _make_placement(parent_frame=parent)
    b = _make_placement(parent_frame=parent)
    assert a == b
    assert hash(a) == hash(b)


@pytest.mark.unit
def test_placement_with_different_parent_frame_is_not_equal() -> None:
    a = _make_placement(parent_frame=uuid4())
    b = _make_placement(parent_frame=uuid4())
    assert a != b


@pytest.mark.unit
def test_placement_with_different_reference_surface_is_not_equal() -> None:
    a = _make_placement(reference_surface=ReferenceSurface.THERMAL_FACE)
    b = _make_placement(reference_surface=ReferenceSurface.OPTIC_CENTER)
    assert a != b


@pytest.mark.unit
def test_placement_lives_in_a_frozenset() -> None:
    """Pinned: hashable + frozen so a frozenset of Placements works
    (mirrors the AssetPort frozenset usage)."""
    p = _make_placement()
    assert p in {p}
