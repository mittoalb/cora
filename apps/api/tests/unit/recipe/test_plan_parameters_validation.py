"""Unit tests for the Plan parameter_defaults validator (Phase 6g-b).

Validates dicts against a Method's parameters_schema using
jsonschema-rs. Permissive when the schema is None (locked posture
per [[project_run_parameters_design]] §6g-b).
"""

from typing import Any

import pytest

from cora.recipe.aggregates.plan import (
    InvalidPlanParameterDefaultsError,
    validate_parameter_defaults_against_method_schema,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(**body: Any) -> dict[str, Any]:
    return {"$schema": _DRAFT, **body}


@pytest.mark.unit
def test_passes_when_schema_is_none_and_defaults_is_empty() -> None:
    """Empty + no schema = trivially valid."""
    validate_parameter_defaults_against_method_schema({}, None)


@pytest.mark.unit
def test_passes_when_schema_is_none_and_defaults_is_non_empty() -> None:
    """Permissive: Method declares no contract -> any defaults accepted.
    Asymmetric vs 5g-c (zero-Capabilities + non-empty settings -> reject).
    Pinned per the 6g-b locked design."""
    validate_parameter_defaults_against_method_schema({"anything": 42}, None)


@pytest.mark.unit
def test_passes_when_defaults_match_schema() -> None:
    schema = _schema(
        type="object",
        properties={"energy_kev": {"type": "number", "minimum": 5, "maximum": 50}},
    )
    validate_parameter_defaults_against_method_schema({"energy_kev": 12.0}, schema)


@pytest.mark.unit
def test_passes_when_defaults_is_empty_even_with_schema() -> None:
    """Empty defaults satisfy any schema (no required-field check at
    this layer; required applies to effective_parameters at Run start)."""
    schema = _schema(
        type="object",
        required=["energy_kev"],
        properties={"energy_kev": {"type": "number"}},
    )
    validate_parameter_defaults_against_method_schema({}, schema)


@pytest.mark.unit
def test_raises_on_constraint_violation() -> None:
    schema = _schema(
        type="object",
        properties={"energy_kev": {"type": "number", "minimum": 5}},
    )
    with pytest.raises(InvalidPlanParameterDefaultsError) as exc_info:
        validate_parameter_defaults_against_method_schema({"energy_kev": 1.0}, schema)
    assert "validation failed" in exc_info.value.reason


@pytest.mark.unit
def test_raises_on_type_mismatch() -> None:
    schema = _schema(
        type="object",
        properties={"energy_kev": {"type": "number"}},
    )
    with pytest.raises(InvalidPlanParameterDefaultsError):
        validate_parameter_defaults_against_method_schema({"energy_kev": "twelve"}, schema)


@pytest.mark.unit
def test_path_threading_in_error_message() -> None:
    """Error includes the offending key path so operators can fix
    the right key in a multi-key dict."""
    schema = _schema(
        type="object",
        properties={
            "energy_kev": {"type": "number", "minimum": 5},
            "exposure_ms": {"type": "integer", "minimum": 1},
        },
    )
    with pytest.raises(InvalidPlanParameterDefaultsError) as exc_info:
        validate_parameter_defaults_against_method_schema(
            {"energy_kev": 12.0, "exposure_ms": -5}, schema
        )
    assert "exposure_ms" in exc_info.value.reason
