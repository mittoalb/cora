"""Property-based tests for the Placement value object.

Complements `test_placement_value_object.py` (example-based) with
universal claims over the generated input space:

  - For any valid 13-tuple, construction succeeds and round-trips.
  - For any negative tolerance on any of the six axes, construction
    raises InvalidPlacementError.
  - Equal-by-tuple Placements share a hash (frozenset dedup).
  - Round-trip identity: a Placement reconstructed from its fields
    equals the original.
"""

from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates._placement import (
    InvalidPlacementError,
    Placement,
    ReferenceSurface,
    UnitSystem,
)

_FINITE_FLOAT = st.floats(
    allow_nan=False,
    allow_infinity=False,
    min_value=-1e9,
    max_value=1e9,
)
_NON_NEGATIVE_FLOAT = st.floats(
    allow_nan=False,
    allow_infinity=False,
    min_value=0.0,
    max_value=1e9,
)
_NEGATIVE_FLOAT = st.floats(
    allow_nan=False,
    allow_infinity=False,
    min_value=-1e9,
    max_value=-1e-12,
)
_UUID = st.uuids()
_REF_SURFACE = st.sampled_from(list(ReferenceSurface))
_UNITS = st.sampled_from(list(UnitSystem))


def _placement_kwargs(
    *,
    x: float,
    y: float,
    z: float,
    rx: float,
    ry: float,
    rz: float,
    parent_frame_id: UUID,
    reference_surface: ReferenceSurface,
    tol_x: float,
    tol_y: float,
    tol_z: float,
    tol_rx: float,
    tol_ry: float,
    tol_rz: float,
    units: UnitSystem,
) -> dict[str, object]:
    return {
        "x": x,
        "y": y,
        "z": z,
        "rx": rx,
        "ry": ry,
        "rz": rz,
        "parent_frame_id": parent_frame_id,
        "reference_surface": reference_surface,
        "tol_x": tol_x,
        "tol_y": tol_y,
        "tol_z": tol_z,
        "tol_rx": tol_rx,
        "tol_ry": tol_ry,
        "tol_rz": tol_rz,
        "units": units,
    }


@pytest.mark.unit
@given(
    x=_FINITE_FLOAT,
    y=_FINITE_FLOAT,
    z=_FINITE_FLOAT,
    rx=_FINITE_FLOAT,
    ry=_FINITE_FLOAT,
    rz=_FINITE_FLOAT,
    parent_frame_id=_UUID,
    reference_surface=_REF_SURFACE,
    tol_x=_NON_NEGATIVE_FLOAT,
    tol_y=_NON_NEGATIVE_FLOAT,
    tol_z=_NON_NEGATIVE_FLOAT,
    tol_rx=_NON_NEGATIVE_FLOAT,
    tol_ry=_NON_NEGATIVE_FLOAT,
    tol_rz=_NON_NEGATIVE_FLOAT,
    units=_UNITS,
)
def test_placement_constructs_for_any_valid_input(
    x: float,
    y: float,
    z: float,
    rx: float,
    ry: float,
    rz: float,
    parent_frame_id: UUID,
    reference_surface: ReferenceSurface,
    tol_x: float,
    tol_y: float,
    tol_z: float,
    tol_rx: float,
    tol_ry: float,
    tol_rz: float,
    units: UnitSystem,
) -> None:
    """Any valid 13-tuple builds and round-trips its fields."""
    p = Placement(
        **_placement_kwargs(  # type: ignore[arg-type]
            x=x,
            y=y,
            z=z,
            rx=rx,
            ry=ry,
            rz=rz,
            parent_frame_id=parent_frame_id,
            reference_surface=reference_surface,
            tol_x=tol_x,
            tol_y=tol_y,
            tol_z=tol_z,
            tol_rx=tol_rx,
            tol_ry=tol_ry,
            tol_rz=tol_rz,
            units=units,
        )
    )
    assert p.x == x
    assert p.parent_frame_id == parent_frame_id
    assert p.reference_surface is reference_surface
    assert p.units is units
    assert p.tol_z == tol_z


@pytest.mark.unit
@given(
    axis=st.sampled_from(["tol_x", "tol_y", "tol_z", "tol_rx", "tol_ry", "tol_rz"]),
    bad_value=_NEGATIVE_FLOAT,
)
def test_placement_rejects_negative_tolerance_on_any_axis(axis: str, bad_value: float) -> None:
    """Any negative tolerance on any of the six axes raises with the
    offending field name in the reason."""
    base: dict[str, object] = {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
        "rx": 0.0,
        "ry": 0.0,
        "rz": 0.0,
        "parent_frame_id": uuid4(),
        "reference_surface": ReferenceSurface.OPTIC_CENTER,
        "tol_x": 0.0,
        "tol_y": 0.0,
        "tol_z": 0.0,
        "tol_rx": 0.0,
        "tol_ry": 0.0,
        "tol_rz": 0.0,
        "units": UnitSystem.SI_MM_RAD,
    }
    base[axis] = bad_value
    with pytest.raises(InvalidPlacementError) as info:
        Placement(**base)  # type: ignore[arg-type]
    assert axis in info.value.reason


@pytest.mark.unit
@given(
    x=_FINITE_FLOAT,
    y=_FINITE_FLOAT,
    z=_FINITE_FLOAT,
    rx=_FINITE_FLOAT,
    ry=_FINITE_FLOAT,
    rz=_FINITE_FLOAT,
    parent_frame_id=_UUID,
    reference_surface=_REF_SURFACE,
    tol_x=_NON_NEGATIVE_FLOAT,
    tol_y=_NON_NEGATIVE_FLOAT,
    tol_z=_NON_NEGATIVE_FLOAT,
    tol_rx=_NON_NEGATIVE_FLOAT,
    tol_ry=_NON_NEGATIVE_FLOAT,
    tol_rz=_NON_NEGATIVE_FLOAT,
    units=_UNITS,
)
def test_equal_placements_collapse_in_a_frozenset(
    x: float,
    y: float,
    z: float,
    rx: float,
    ry: float,
    rz: float,
    parent_frame_id: UUID,
    reference_surface: ReferenceSurface,
    tol_x: float,
    tol_y: float,
    tol_z: float,
    tol_rx: float,
    tol_ry: float,
    tol_rz: float,
    units: UnitSystem,
) -> None:
    """Two structurally identical Placements share a hash and a
    frozenset deduplicates them. NaN inputs are excluded upstream
    by the `_FINITE_FLOAT` / `_NON_NEGATIVE_FLOAT` strategies
    (`allow_nan=False`), so no explicit NaN guard is needed here."""
    kw = _placement_kwargs(
        x=x,
        y=y,
        z=z,
        rx=rx,
        ry=ry,
        rz=rz,
        parent_frame_id=parent_frame_id,
        reference_surface=reference_surface,
        tol_x=tol_x,
        tol_y=tol_y,
        tol_z=tol_z,
        tol_rx=tol_rx,
        tol_ry=tol_ry,
        tol_rz=tol_rz,
        units=units,
    )
    p1 = Placement(**kw)  # type: ignore[arg-type]
    p2 = Placement(**kw)  # type: ignore[arg-type]
    assert p1 == p2
    assert hash(p1) == hash(p2)
    assert frozenset({p1, p2}) == frozenset({p1})
