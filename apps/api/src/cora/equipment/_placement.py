"""Placement value object: where a Mount or Frame sits in space.

A Placement is the complete answer to "where is this thing and how
is it oriented?" It is a flat 6-degrees-of-freedom pose (three
position axes + three rotation axes) plus three additional pieces
of information that make the pose interpretable across surveys and
re-installations:

  - `parent_frame`: which coordinate frame the values are measured
    against (the 1.35 mrad standard beam centerline, an alternate
    centerline at the mirror, the optical-bench frame on a table, ...).
  - `reference_surface`: which physical feature of the part the
    position values were measured from (the upstream face of the
    thermal block, the center of the optic, the upstream face of the
    shielding). Without this, "z = 259313" is ambiguous.
  - `units`: the unit system the values are stored in. CORA stores
    canonically; conversion happens at the edge per
    `project_units_design.md`.

Tolerances are bilateral (symmetric ±) per axis. Per-axis tolerance
must be non-negative; zero means "exact." Asymmetric, projected,
MMC/LMC, and zone-shaped tolerances per ISO 1101 / ASME Y14.5 are
deferred (Watch item in `project_mount_frame_design.md`).

Flat 6-DoF is the v1 shape; the IFC `IfcLocalPlacement` is its
ancestor (parent-pointer + relative orientation). Promote to a
NeXus NXtransformations-style ordered axis-chain only when
articulated multi-DoF kinematics surface (Watch item).

`ReferenceSurface` is a closed StrEnum of three values; escape hatch
when a second facility lands and a fourth convention surfaces. NOT
a GD&T datum (which is the derived theoretical entity); these are
"datum features" in GD&T parlance. CORA uses the longer
`ReferenceSurface` to avoid the term collision.

`UnitSystem` is a StrEnum with one v1 value (`SI_MM_RAD`):
millimetres for translation, radians for rotation. Extensible when
non-SI deployments land.

`Placement` is a closed-shape typed frozen dataclass. NOT
`json_schema_validation` (that pattern is for declarer-owns-schema /
carrier-owns-dict); validation lives in field shape + enum
membership + `__post_init__` checks.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.equipment.errors import InvalidPlacementError


class ReferenceSurface(StrEnum):
    """The physical feature of a part that a Placement is measured FROM.

    APS 2-BM uses three conventions documented in the reference
    table (APS_1404611):
      - `THERMAL_FACE`: upstream face of the thermal component (front-
        end masks, beam stops, photon stops, Be windows; OFHC Cu /
        Be sit between cooling water and beam).
      - `OPTIC_CENTER`: center of the optic (mirror axis, monochromator
        crystal axis; the active surface, not a face).
      - `SHIELDING_FACE`: upstream face of the shielding material
        (collimators, baffles; the W or Pb absorbing surface).

    Closed enum v1; CORA precedent is the Affordance StrEnum. Add a
    fourth value only when a second facility surveyed against a
    convention not in the v1 set.
    """

    THERMAL_FACE = "ThermalFace"
    OPTIC_CENTER = "OpticCenter"
    SHIELDING_FACE = "ShieldingFace"


class UnitSystem(StrEnum):
    """The unit system a Placement's values are stored in.

    v1 ships with one value (`SI_MM_RAD`): translation in millimetres,
    rotation in radians. CORA stores canonically; conversion to or
    from facility-local units happens at the adapter boundary per
    `project_units_design.md` (canonical-stored, convert-at-edge).

    The single v1 value is what makes the design memo's
    "tolerance units MUST match value units per axis" invariant
    structurally satisfied: with one UnitSystem, a Placement's
    tolerances are by construction in the same units as its
    values. When a second UnitSystem lands (non-SI deployment),
    the per-axis coupling check must move from "trivially true" to
    an explicit `__post_init__` validation, OR Placement must widen
    to per-axis units fields. Capture this gate before widening
    the enum.
    """

    SI_MM_RAD = "SI_mm_rad"


@dataclass(frozen=True)
class Placement:
    """The pose (position + orientation) of a Mount or Frame.

    Flat 6 degrees of freedom: three translations (x, y, z) and
    three rotations (rx, ry, rz). Each value carries an independent
    `±` tolerance. All twelve numeric values are in the system named
    by `units` (v1: millimetres for translation, radians for rotation).

    `parent_frame` names the coordinate frame the values are measured
    against. `reference_surface` names the physical feature on the
    part the position is measured FROM.

    Equality and hash are structural across all 15 fields, so a
    Placement can live unambiguously in a frozenset.
    """

    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float
    parent_frame: UUID
    reference_surface: ReferenceSurface
    tol_x: float
    tol_y: float
    tol_z: float
    tol_rx: float
    tol_ry: float
    tol_rz: float
    units: UnitSystem

    def __post_init__(self) -> None:
        # Pure validation, no normalization (no trim or
        # `object.__setattr__` dance): all fields are typed
        # primitives or enums; only tolerance non-negativity is
        # not encodable in the type itself.
        for axis_name, value in (
            ("tol_x", self.tol_x),
            ("tol_y", self.tol_y),
            ("tol_z", self.tol_z),
            ("tol_rx", self.tol_rx),
            ("tol_ry", self.tol_ry),
            ("tol_rz", self.tol_rz),
        ):
            if value < 0:
                raise InvalidPlacementError(
                    f"tolerance {axis_name!s} must be non-negative (got: {value!r})"
                )


__all__ = [
    "Placement",
    "ReferenceSurface",
    "UnitSystem",
]
