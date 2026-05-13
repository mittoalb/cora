"""Unit tests for the Capability settings_schema validator.

Phase 5g-a. Pins the constrained JSON Schema subset CORA accepts:
$schema, type, required, properties, enum, minimum, maximum,
pattern. Every other JSON Schema keyword (including $ref, oneOf,
anyOf, allOf, conditionals, additionalProperties) is rejected.
"""

from typing import Any

import pytest

from cora.equipment.aggregates.capability.schema_validation import (
    InvalidCapabilitySchemaError,
    validate_settings_schema,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(**body: Any) -> dict[str, Any]:
    """Helper: build a schema dict with the required $schema declaration."""
    return {"$schema": _DRAFT, **body}


@pytest.mark.unit
def test_accepts_minimal_object_schema() -> None:
    validate_settings_schema(_schema(type="object"))


@pytest.mark.unit
def test_accepts_full_subset() -> None:
    """Every keyword in the allowed subset should pass — sanity that
    the whitelist matches reality."""
    validate_settings_schema(
        _schema(
            type="object",
            required=["energy_kev"],
            properties={
                "energy_kev": {"type": "number", "minimum": 5, "maximum": 50},
                "filter_material": {"type": "string", "enum": ["Cu", "Al", "Mo"]},
                "exposure_ms": {"type": "integer", "minimum": 1, "maximum": 5000},
                "detector_serial": {"type": "string", "pattern": "^FLIR-[0-9]+$"},
            },
        )
    )


@pytest.mark.unit
def test_rejects_missing_dollar_schema() -> None:
    """The $schema field is required — pins the draft explicitly so
    jsonschema-rs version changes can't silently flip the default."""
    with pytest.raises(InvalidCapabilitySchemaError) as exc_info:
        validate_settings_schema({"type": "object"})
    assert "$schema must be exactly" in exc_info.value.reason


@pytest.mark.unit
def test_rejects_wrong_dollar_schema_uri() -> None:
    with pytest.raises(InvalidCapabilitySchemaError) as exc_info:
        validate_settings_schema(
            {
                "$schema": "https://json-schema.org/draft-07/schema#",
                "type": "object",
            }
        )
    assert "$schema must be exactly" in exc_info.value.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "forbidden_key",
    ["$ref", "oneOf", "anyOf", "allOf", "not", "if", "additionalProperties"],
)
def test_rejects_forbidden_top_level_keyword(forbidden_key: str) -> None:
    """Anti-feature pinning: every keyword OUTSIDE the subset must
    raise. Catches a future contributor from quietly extending the
    surface area."""
    with pytest.raises(InvalidCapabilitySchemaError) as exc_info:
        validate_settings_schema(_schema(**{forbidden_key: True}))
    assert "forbidden keyword" in exc_info.value.reason
    assert forbidden_key in exc_info.value.reason


@pytest.mark.unit
def test_rejects_forbidden_keyword_nested_in_properties() -> None:
    """Recursive subset enforcement: forbidden keywords inside
    properties values also raise."""
    with pytest.raises(InvalidCapabilitySchemaError) as exc_info:
        validate_settings_schema(_schema(type="object", properties={"x": {"$ref": "#/defs/foo"}}))
    assert "$ref" in exc_info.value.reason
    assert "properties.x" in exc_info.value.reason


@pytest.mark.unit
def test_rejects_properties_value_that_is_not_a_dict() -> None:
    with pytest.raises(InvalidCapabilitySchemaError) as exc_info:
        validate_settings_schema(_schema(type="object", properties={"x": "not-a-schema"}))
    assert "must be a schema dict" in exc_info.value.reason


@pytest.mark.unit
def test_rejects_properties_that_is_not_a_dict() -> None:
    with pytest.raises(InvalidCapabilitySchemaError) as exc_info:
        validate_settings_schema(_schema(type="object", properties=["a", "b"]))
    assert "must be a dict" in exc_info.value.reason


@pytest.mark.unit
def test_accepts_empty_properties_dict() -> None:
    """`{} properties` is structurally valid and means 'this object
    declares no specific properties'."""
    validate_settings_schema(_schema(type="object", properties={}))


@pytest.mark.unit
def test_accepts_nested_properties_with_subset_only() -> None:
    """Nested properties values may themselves use the full subset
    (including their own properties + $schema is harmless)."""
    validate_settings_schema(
        _schema(
            type="object",
            properties={
                "alignment": {
                    "type": "object",
                    "properties": {
                        "pitch_urad": {"type": "number"},
                        "roll_urad": {"type": "number"},
                    },
                    "required": ["pitch_urad"],
                },
            },
        )
    )


@pytest.mark.unit
def test_accepts_nested_dollar_schema_declaration() -> None:
    """Nested property-schemas may carry their own `$schema` even
    though only the root NEEDS one. Pinned deliberately: the validator
    treats `$schema` as harmless at every depth (allowing it nested
    keeps the recursion API simple). If a future change tightens this
    to root-only, this test should flip to `pytest.raises`."""
    validate_settings_schema(
        _schema(
            type="object",
            properties={
                "alignment": {
                    "$schema": _DRAFT,
                    "type": "object",
                    "properties": {"pitch_urad": {"type": "number"}},
                },
            },
        )
    )


@pytest.mark.unit
def test_rejects_malformed_schema_via_jsonschema_rs() -> None:
    """If the schema is in-subset but jsonschema-rs rejects it as
    malformed (for example, an invalid `pattern` regex), we surface
    that as InvalidCapabilitySchemaError — write-time guard."""
    with pytest.raises(InvalidCapabilitySchemaError) as exc_info:
        validate_settings_schema(
            _schema(
                type="object",
                properties={"x": {"type": "string", "pattern": "[invalid(regex"}},
            )
        )
    assert "Invalid Capability settings_schema" in str(exc_info.value)
