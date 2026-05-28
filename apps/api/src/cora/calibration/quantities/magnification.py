"""Objective-lens magnification calibration: operating_point + value schemas.

Optical magnification of a microscope objective at the sample plane is
strictly a measured number per installation. The vendor nameplate label
(`"10x_Mitutoyo"`) lives in `operating_point.objective_designation`; the
calibrated reality (often ~3-5% off nominal) lives in
`value.magnification`. Object-to-image direction convention: the
standard microscopy definition where magnification = sensor pixel size
divided by measured object-side pixel size.

The same physical objective at different X-ray energies gets distinct
revision chains because magnification varies weakly with energy through
beam divergence and chromatic effects in the optical relay.

Operating point keys:
  - `objective_designation` (string, 1-100 chars): the vendor / nameplate
    identifier (`"10x_Mitutoyo"`, `"5x_Optique_Peter"`). Operator-supplied
    tag rather than numeric magnification because the same numeric value
    can refer to physically different optics across vendors or upgrades.
    Named `objective_designation` rather than `optics_config` (the term
    used in `rotation_center` / `detector_pixel_size`) because a
    magnification calibration is specifically about ONE objective lens;
    the rotation-axis center and detector pixel size are properties of
    the entire optical-chain configuration. Same operator-tag string
    convention; different specificity.
  - `energy` (number, 1-100, multipleOf 0.001): X-ray energy at which
    the magnification was measured. REQUIRED (unlike
    `detector_pixel_size` where it is optional) because magnification
    varies measurably with energy through chromatic effects in the
    optical relay.

Value keys:
  - `magnification` (number, > 0): the calibrated magnification.
    Dimensionless (UDUNITS `1`). Permits values below 1 to cover
    de-magnification optics in tandem-lens scintillator-relay paths.
  - `uncertainty` (number, optional, minimum 0): operator-supplied or
    method-supplied 1-sigma uncertainty; dimensionless.
"""

from typing import Any

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

OPERATING_POINT_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "objective_designation": {
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
    "required": ["objective_designation", "energy"],
    "additionalProperties": False,
}

VALUE_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "magnification": {
            "type": "number",
            "exclusiveMinimum": 0,
            "unit": {"system": "udunits", "code": "1"},
        },
        "uncertainty": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "1"},
        },
    },
    "required": ["magnification"],
    "additionalProperties": False,
}

__all__ = ["OPERATING_POINT_SCHEMA", "VALUE_SCHEMA"]
