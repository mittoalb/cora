"""Per-quantity schema registry tests.

Pins the closed-catalog invariant: every `CalibrationQuantity` enum
value MUST have a registered operating_point_schema + value_schema,
and each schema MUST follow the design memo's anti-hooks
(`additionalProperties: False` per Round 2 NXcalibration cautionary
tale; primitive types only at operating_point per Q1 lock).
"""

from typing import Any

import pytest

from cora.calibration.quantities import (
    CalibrationQuantity,
    get_operating_point_schema,
    get_value_schema,
)


@pytest.mark.unit
def test_every_quantity_has_registered_operating_point_schema() -> None:
    """Anti-drift: when a new CalibrationQuantity value lands, the
    registry MUST be extended in the same PR."""
    for quantity in CalibrationQuantity:
        schema = get_operating_point_schema(quantity)
        assert isinstance(schema, dict)
        assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"


@pytest.mark.unit
def test_every_quantity_has_registered_value_schema() -> None:
    for quantity in CalibrationQuantity:
        schema = get_value_schema(quantity)
        assert isinstance(schema, dict)
        assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"


@pytest.mark.unit
def test_every_operating_point_schema_is_closed() -> None:
    """Per Q1 lock + NXcalibration cautionary tale: closed at the
    contract layer; no `additionalProperties` drift."""
    for quantity in CalibrationQuantity:
        schema = get_operating_point_schema(quantity)
        assert schema.get("additionalProperties") is False, (
            f"{quantity.value} operating_point_schema must declare `additionalProperties: False`"
        )


@pytest.mark.unit
def test_every_value_schema_is_closed() -> None:
    for quantity in CalibrationQuantity:
        schema = get_value_schema(quantity)
        assert schema.get("additionalProperties") is False, (
            f"{quantity.value} value_schema must declare `additionalProperties: False`"
        )


@pytest.mark.unit
def test_every_operating_point_schema_declares_required() -> None:
    """All v1 quantities have required identity keys; without them,
    `operating_point = {}` would silently match every prior calibration."""
    for quantity in CalibrationQuantity:
        schema = get_operating_point_schema(quantity)
        required: object = schema.get("required", [])
        assert isinstance(required, list) and len(required) > 0, (  # pyright: ignore[reportUnknownArgumentType]
            f"{quantity.value} operating_point_schema must declare at least one required key"
        )


@pytest.mark.unit
def test_every_value_schema_declares_required() -> None:
    for quantity in CalibrationQuantity:
        schema = get_value_schema(quantity)
        required: object = schema.get("required", [])
        assert isinstance(required, list) and len(required) > 0  # pyright: ignore[reportUnknownArgumentType]


@pytest.mark.unit
def test_rotation_center_operating_point_shape() -> None:
    """Spot-check the rotation_center schema declares the design-memo
    operating-point keys (energy + optics_config)."""
    schema = get_operating_point_schema(CalibrationQuantity.ROTATION_CENTER)
    properties: dict[str, Any] = schema.get("properties", {})
    assert set(properties.keys()) == {"energy", "optics_config"}
    assert "energy" in schema["required"]
    assert "optics_config" in schema["required"]


@pytest.mark.unit
def test_rotation_center_value_shape() -> None:
    schema = get_value_schema(CalibrationQuantity.ROTATION_CENTER)
    properties: dict[str, Any] = schema.get("properties", {})
    assert "center" in properties
    assert "center" in schema["required"]


@pytest.mark.unit
def test_detector_pixel_size_operating_point_shape() -> None:
    schema = get_operating_point_schema(CalibrationQuantity.DETECTOR_PIXEL_SIZE)
    properties: dict[str, Any] = schema.get("properties", {})
    assert "optics_config" in properties
    assert "optics_config" in schema["required"]


@pytest.mark.unit
def test_detector_pixel_size_value_shape() -> None:
    schema = get_value_schema(CalibrationQuantity.DETECTOR_PIXEL_SIZE)
    properties: dict[str, Any] = schema.get("properties", {})
    assert "pixel_size" in properties
    assert "pixel_size" in schema["required"]


@pytest.mark.unit
def test_magnification_operating_point_shape() -> None:
    schema = get_operating_point_schema(CalibrationQuantity.MAGNIFICATION)
    properties: dict[str, Any] = schema.get("properties", {})
    assert set(properties.keys()) == {"objective_designation", "energy"}
    assert "objective_designation" in schema["required"]
    assert "energy" in schema["required"]


@pytest.mark.unit
def test_magnification_value_shape() -> None:
    schema = get_value_schema(CalibrationQuantity.MAGNIFICATION)
    properties: dict[str, Any] = schema.get("properties", {})
    assert "magnification" in properties
    assert "magnification" in schema["required"]
    assert properties["magnification"].get("exclusiveMinimum") == 0


@pytest.mark.unit
def test_effective_thickness_operating_point_shape() -> None:
    schema = get_operating_point_schema(CalibrationQuantity.EFFECTIVE_THICKNESS)
    properties: dict[str, Any] = schema.get("properties", {})
    assert set(properties.keys()) == {"scintillator_material", "energy"}
    assert "scintillator_material" in schema["required"]
    assert "energy" in schema["required"]


@pytest.mark.unit
def test_effective_thickness_value_shape() -> None:
    schema = get_value_schema(CalibrationQuantity.EFFECTIVE_THICKNESS)
    properties: dict[str, Any] = schema.get("properties", {})
    assert "effective_thickness" in properties
    assert "effective_thickness" in schema["required"]
    assert properties["effective_thickness"].get("exclusiveMinimum") == 0
