"""Detector pixel-size calibration: operating_point + value schemas.

Effective pixel size at the sample plane depends on the lens
magnification and (weakly) on the X-ray energy via beam divergence.
Measured by ruling-mask procedures or extracted from reconstructed
images (`pixel_size_from_target` family of methods).

Operating point keys:
  - `optics_config` (string): the lens / objective configuration; same
    string identifiers as rotation_center for consistency.
  - `energy_keV` (number, optional): some setups report pixel size as
    energy-independent (parallel-beam approximation); others vary
    slightly with energy. Optional so the same calibration can cover
    a band of energies when valid.

Value keys:
  - `pixel_size_um` (number, > 0): effective pixel size at the sample
    plane, in micrometers.
  - `uncertainty_um` (number, optional, minimum 0): 1-sigma uncertainty.
"""

from typing import Any

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

OPERATING_POINT_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "optics_config": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
        "energy_keV": {
            "type": "number",
            "minimum": 1,
            "maximum": 100,
            "multipleOf": 0.001,
            "unit": {"system": "udunits", "code": "keV"},
        },
    },
    "required": ["optics_config"],
    "additionalProperties": False,
}

VALUE_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "pixel_size_um": {
            "type": "number",
            "exclusiveMinimum": 0,
            "unit": {"system": "udunits", "code": "um"},
        },
        "uncertainty_um": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "um"},
        },
    },
    "required": ["pixel_size_um"],
    "additionalProperties": False,
}

__all__ = ["OPERATING_POINT_SCHEMA", "VALUE_SCHEMA"]
