"""Scintillator effective-thickness calibration: operating_point + value schemas.

The effective thickness of a scintillator is the energy-deposition-weighted
path length that contributes to detected light. It is not the nominal
mechanical thickness on the vendor datasheet; it varies with X-ray
energy (through the attenuation length in the scintillator material) and
with operating conditions. Effective thickness drives the
energy-resolution / spatial-resolution trade-off and is load-bearing for
quantitative reconstruction.

Operating point keys:
  - `scintillator_material` (string, 1-100 chars): the scintillator
    compound (`"LuAG"`, `"GAGG"`, `"YAG"`, `"CdWO4"`). Same material at
    different energies gets distinct revision chains. Material identity
    is operator-supplied and conventionally lives in the scintillator
    Asset's `name` field (the `Scintillator` Family carries `thickness`
    + `decay_time` only, not a material field); the value flows through
    to `operating_point` at calibration-registration time.
  - `energy` (number, 1-100, multipleOf 0.001): X-ray energy at which
    the effective thickness was measured. REQUIRED (unlike
    `detector_pixel_size` where it is optional) because the X-ray
    attenuation length in the scintillator changes substantially with
    energy, making same-material-different-energy a distinct calibration
    target.

Value keys:
  - `effective_thickness` (number, > 0): the calibrated effective
    thickness in micrometers.
  - `uncertainty` (number, optional, minimum 0): 1-sigma uncertainty
    in micrometers.
"""

from typing import Any

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

OPERATING_POINT_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "scintillator_material": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
        "energy": {
            "type": "number",
            "minimum": 1,
            "maximum": 100,
            "multipleOf": 0.001,
            "unit": {"system": "udunits", "code": "keV"},
        },
    },
    "required": ["scintillator_material", "energy"],
    "additionalProperties": False,
}

VALUE_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "effective_thickness": {
            "type": "number",
            "exclusiveMinimum": 0,
            "unit": {"system": "udunits", "code": "um"},
        },
        "uncertainty": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "um"},
        },
    },
    "required": ["effective_thickness"],
    "additionalProperties": False,
}

__all__ = ["OPERATING_POINT_SCHEMA", "VALUE_SCHEMA"]
