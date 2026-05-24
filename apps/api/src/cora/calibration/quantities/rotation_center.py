"""Rotation-axis center calibration: operating_point + value schemas.

The rotation-axis center is the pixel coordinate where the sample's
rotation axis projects onto the detector. Computed by alignment
Procedures (operator-visual sphere centroid, live-tomostream readout)
or post-acquisition numerical methods (`tomopy.find_center_vo`).

Operating point keys:
  - `energy` (number, 1-100, multipleOf 0.001): X-ray energy at
    which the center was measured. Rotation center depends weakly on
    energy via the monochromator's slope; same physical axis at
    different energies gets distinct revision chains.
  - `optics_config` (string): the optical magnification config in use
    (lens position, scintillator-detector geometry). String tag rather
    than a numeric magnification because operators name them ("5x",
    "10x", "high-resolution") and the same numeric value can mean
    different physical configs across upgrades.

Value keys:
  - `center` (number): the rotation-axis pixel coordinate on the
    detector (typically near sensor_width / 2).
  - `uncertainty` (number, optional, minimum 0): operator-supplied or
    method-supplied 1-sigma uncertainty; if absent, downstream consumers
    treat as unknown.
"""

from typing import Any

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

OPERATING_POINT_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "energy": {
            "type": "number",
            "minimum": 1,
            "maximum": 100,
            "multipleOf": 0.001,
            "unit": {"system": "udunits", "code": "keV"},
        },
        "optics_config": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
    },
    "required": ["energy", "optics_config"],
    "additionalProperties": False,
}

VALUE_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "center": {
            "type": "number",
            "unit": {"system": "udunits", "code": "pixel"},
        },
        "uncertainty": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "pixel"},
        },
    },
    "required": ["center"],
    "additionalProperties": False,
}

__all__ = ["OPERATING_POINT_SCHEMA", "VALUE_SCHEMA"]
