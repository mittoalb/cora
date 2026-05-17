"""Unit-tier coverage for the 4 pilot Capability schemas + device values.

Phase 10e-a sibling tests. The integration scenario at
`tests/integration/scenarios/test_2bm_alignment_center.py`
exercises these schemas + values end-to-end. These unit tests pin
the schema-by-schema validator behavior at a faster tier:

  - Each pilot schema parses cleanly as a Capability settings_schema
    (subset + unit annotations both valid).
  - Each pilot device-value dict passes cross-Capability validation
    against its declaring schema.
  - One pilot-specific boundary check per Capability (negative
    max_speed rejected, missing required key rejected, etc.) -- not
    duplicating the validator's own test suite, but pinning the
    bounds the pilot schemas declare are actually enforced.

Schemas + values are duplicated from the scenario file rather than
imported. Cross-tier import would couple unit tests to integration
test internals; the design memo's "DO NOT extract before rule-of-
three" anti-hook applies. If a third consumer appears (a contract
test, a second beamline scenario), extract then.
"""

from typing import Any
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset.settings_validation import (
    validate_settings_against_capabilities,
)
from cora.equipment.aggregates.asset.state import InvalidAssetSettingsError
from cora.equipment.aggregates.capability.settings_validation import (
    InvalidCapabilitySettingsSchemaError,
    validate_settings_schema,
)
from cora.equipment.aggregates.capability.state import (
    Capability,
    CapabilityName,
    CapabilityStatus,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _capability(name: str, schema: dict[str, Any]) -> Capability:
    return Capability(
        id=uuid4(),
        name=CapabilityName(name),
        status=CapabilityStatus.DEFINED,
        settings_schema=schema,
    )


# ---------- RotaryStage ----------


_SCHEMA_ROTARY_STAGE: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "min_position": {"type": "number", "unit": {"system": "udunits", "code": "deg"}},
        "max_position": {"type": "number", "unit": {"system": "udunits", "code": "deg"}},
        "max_speed": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "deg/s"},
        },
        "encoder_resolution": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "deg"},
        },
        "homing_offset": {"type": "number", "unit": {"system": "udunits", "code": "deg"}},
    },
    "required": ["min_position", "max_position", "max_speed", "encoder_resolution"],
}

_SETTINGS_AEROTECH_ABRS: dict[str, Any] = {
    "min_position": -360.0,
    "max_position": 360.0,
    "max_speed": 720.0,
    "encoder_resolution": 0.0001,
    "homing_offset": 0.0,
}


@pytest.mark.unit
def test_rotary_stage_schema_validates() -> None:
    validate_settings_schema(_SCHEMA_ROTARY_STAGE)


@pytest.mark.unit
def test_rotary_stage_device_values_pass() -> None:
    cap = _capability("RotaryStage", _SCHEMA_ROTARY_STAGE)
    validate_settings_against_capabilities(_SETTINGS_AEROTECH_ABRS, [cap])


@pytest.mark.unit
def test_rotary_stage_negative_max_speed_rejected() -> None:
    """max_speed bound: minimum=0 enforces hardware-envelope sanity. match=
    discriminates a bound violation from a generic schema rejection."""
    cap = _capability("RotaryStage", _SCHEMA_ROTARY_STAGE)
    bad = {**_SETTINGS_AEROTECH_ABRS, "max_speed": -1.0}
    with pytest.raises(InvalidAssetSettingsError, match=r"max_speed.*minimum"):
        validate_settings_against_capabilities(bad, [cap])


# ---------- LinearStage ----------


_SCHEMA_LINEAR_STAGE: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "min_position": {"type": "number", "unit": {"system": "udunits", "code": "mm"}},
        "max_position": {"type": "number", "unit": {"system": "udunits", "code": "mm"}},
        "max_speed": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "mm/s"},
        },
        "encoder_resolution": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "mm"},
        },
    },
    "required": ["min_position", "max_position", "max_speed", "encoder_resolution"],
}

_SETTINGS_SAMPLE_TOP_X: dict[str, Any] = {
    "min_position": -10.0,
    "max_position": 10.0,
    "max_speed": 1.0,
    "encoder_resolution": 0.0005,
}


@pytest.mark.unit
def test_linear_stage_schema_validates() -> None:
    validate_settings_schema(_SCHEMA_LINEAR_STAGE)


@pytest.mark.unit
def test_linear_stage_device_values_pass() -> None:
    cap = _capability("LinearStage", _SCHEMA_LINEAR_STAGE)
    validate_settings_against_capabilities(_SETTINGS_SAMPLE_TOP_X, [cap])


@pytest.mark.unit
def test_linear_stage_missing_required_key_rejected() -> None:
    """All 4 of {min/max_position, max_speed, encoder_resolution} are
    required at the schema level. Dropping any one fails validation;
    match= discriminates the missing-required path from generic rejection."""
    cap = _capability("LinearStage", _SCHEMA_LINEAR_STAGE)
    bad = {k: v for k, v in _SETTINGS_SAMPLE_TOP_X.items() if k != "encoder_resolution"}
    with pytest.raises(InvalidAssetSettingsError, match=r"encoder_resolution.*required property"):
        validate_settings_against_capabilities(bad, [cap])


# ---------- Camera ----------


_SCHEMA_CAMERA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "sensor_width": {
            "type": "integer",
            "minimum": 1,
            "unit": {"system": "udunits", "code": "pixel"},
        },
        "sensor_height": {
            "type": "integer",
            "minimum": 1,
            "unit": {"system": "udunits", "code": "pixel"},
        },
        "pixel_size": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "um"},
        },
        "bit_depth": {
            "type": "integer",
            "minimum": 1,
            "unit": {"system": "udunits", "code": "bit"},
        },
    },
    "required": ["sensor_width", "sensor_height", "pixel_size", "bit_depth"],
}

_SETTINGS_ORYX_5MP: dict[str, Any] = {
    "sensor_width": 2448,
    "sensor_height": 2048,
    "pixel_size": 3.45,
    "bit_depth": 12,
}


@pytest.mark.unit
def test_camera_schema_validates() -> None:
    validate_settings_schema(_SCHEMA_CAMERA)


@pytest.mark.unit
def test_camera_device_values_pass() -> None:
    cap = _capability("Camera", _SCHEMA_CAMERA)
    validate_settings_against_capabilities(_SETTINGS_ORYX_5MP, [cap])


@pytest.mark.unit
def test_camera_string_for_pixel_size_rejected() -> None:
    """pixel_size declared as number; string value fails type check.
    Pins that the unit-annotated numeric properties enforce their type;
    match= discriminates the type-violation path."""
    cap = _capability("Camera", _SCHEMA_CAMERA)
    bad = {**_SETTINGS_ORYX_5MP, "pixel_size": "3.45um"}
    with pytest.raises(InvalidAssetSettingsError, match=r"pixel_size.*not of type"):
        validate_settings_against_capabilities(bad, [cap])


# ---------- Scintillator ----------


_SCHEMA_SCINTILLATOR: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "thickness": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "um"},
        },
        "decay_time": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "us"},
        },
    },
    "required": ["thickness", "decay_time"],
}

_SETTINGS_SCINTILLATOR_LUAG: dict[str, Any] = {
    "thickness": 100.0,
    "decay_time": 0.07,
}


@pytest.mark.unit
def test_scintillator_schema_validates() -> None:
    validate_settings_schema(_SCHEMA_SCINTILLATOR)


@pytest.mark.unit
def test_scintillator_device_values_pass() -> None:
    cap = _capability("Scintillator", _SCHEMA_SCINTILLATOR)
    validate_settings_against_capabilities(_SETTINGS_SCINTILLATOR_LUAG, [cap])


@pytest.mark.unit
def test_scintillator_unknown_key_rejected() -> None:
    """STRICT-by-default (per 5g-c): only DECLARED schema keys are allowed.
    A typo like `decay_tyme` doesn't quietly become a no-op; match=
    discriminates the additionalProperties-violation path."""
    cap = _capability("Scintillator", _SCHEMA_SCINTILLATOR)
    bad = {**_SETTINGS_SCINTILLATOR_LUAG, "decay_tyme": 0.07}
    with pytest.raises(InvalidAssetSettingsError, match=r"Additional properties.*decay_tyme"):
        validate_settings_against_capabilities(bad, [cap])


# ---------- Cross-cutting: unit annotation namespace check ----------
#
# Most likely real-world bug class as the pilot schema corpus grows: a
# pilot author copies a `unit` annotation block and typos the `system`
# namespace (e.g., `"udunit"` instead of `"udunits"`). The schema-declarer
# validator catches this at acceptance time, BEFORE any Asset.settings
# value lands. Pin it with a pilot-shape schema so the regression is
# caught at the tier closest to where pilot authors edit.


@pytest.mark.unit
def test_pilot_shape_schema_with_unknown_unit_system_rejected() -> None:
    """A typo in `unit.system` namespace (not in the closed allowlist) must
    fail schema acceptance at define time, not silently accept and surface
    later at first settings write. match= discriminates the namespace path."""
    bad_schema: dict[str, Any] = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "rotation_step": {
                "type": "number",
                "unit": {"system": "made_up_namespace", "code": "deg"},
            },
        },
        "required": ["rotation_step"],
    }
    with pytest.raises(
        InvalidCapabilitySettingsSchemaError,
        match=r"unit\.system.*made_up_namespace.*not in",
    ):
        validate_settings_schema(bad_schema)
