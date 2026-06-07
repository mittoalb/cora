"""The `DefineCalibration` command — intent dataclass for this slice.

Carries caller-controlled inputs for defining a new Calibration:

  - `target_id` — what this calibration is OF (typically
    Asset.id; the rotation_center "of" the rotary stage). Bare UUID
    reference; existence NOT verified at the decider per the cross-BC
    eventual-consistency stance.
  - `quantity` — closed `CalibrationQuantity` StrEnum value identifying
    the physical quantity (`rotation_center`, `detector_pixel_size`,
    etc.). Each value has a registered operating_point_schema +
    value_schema at `cora.calibration.quantities`.
  - `operating_point` — JSON-shaped dict describing the operating
    regime (energy, optics_config, etc.). Validated STRICT against the
    quantity's operating_point_schema at the decider per the schema-
    validated-values pattern; `additionalProperties: False` rejects
    drift.
  - `description` — optional operator-prose notes (0-2000 chars after
    trim; matches Method/Plan/Family precedent). Empty / whitespace-
    only collapses to None at the slice boundary.

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids, defined_by) are injected by the
handler from infrastructure ports / the request envelope.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cora.calibration.quantities import CalibrationQuantity


@dataclass(frozen=True)
class DefineCalibration:
    """Define a new Calibration (genesis)."""

    target_id: UUID
    quantity: CalibrationQuantity
    operating_point: dict[str, Any]
    description: str | None = None
