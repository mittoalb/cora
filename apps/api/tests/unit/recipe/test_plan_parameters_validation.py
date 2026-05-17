"""Unit tests for the Plan default_parameters validator (Phase 6g-b).

Validates dicts against a Method's parameters_schema using
jsonschema-rs. STRICT when the schema is None — non-empty defaults
without a declared schema raise InvalidPlanDefaultParametersError
(post-6g audit reversal; aligns with 5g-c, Ajv strict-by-default,
and Argo Workflows declared-parameters precedent).
"""

from typing import Any

import pytest

from cora.recipe.aggregates.plan import (
    InvalidPlanDefaultParametersError,
    validate_default_parameters_against_method_schema,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(**body: Any) -> dict[str, Any]:
    return {"$schema": _DRAFT, **body}


@pytest.mark.unit
def test_passes_when_schema_is_none_and_defaults_is_empty() -> None:
    """Empty + no schema = trivially valid."""
    validate_default_parameters_against_method_schema({}, None)


@pytest.mark.unit
def test_raises_when_schema_is_none_and_defaults_is_non_empty() -> None:
    """Strict (post-6g audit reversal): Method declares no contract
    AND defaults supplied -> reject. Operator must declare schema
    (an empty `{}` works for parameter-less Methods) or omit defaults.
    Aligns with 5g-c's strict zero-Capabilities posture and Ajv /
    Argo Workflows community precedent."""
    with pytest.raises(InvalidPlanDefaultParametersError) as exc_info:
        validate_default_parameters_against_method_schema({"anything": 42}, None)
    assert "Method declares no parameters_schema" in exc_info.value.reason
    assert "'anything'" in exc_info.value.reason


@pytest.mark.unit
def test_passes_when_defaults_match_schema() -> None:
    schema = _schema(
        type="object",
        properties={
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            }
        },
    )
    validate_default_parameters_against_method_schema({"energy": 12.0}, schema)


@pytest.mark.unit
def test_passes_when_defaults_is_empty_even_with_schema() -> None:
    """Empty defaults satisfy any schema (no required-field check at
    this layer; required applies to effective_parameters at Run start)."""
    schema = _schema(
        type="object",
        required=["energy"],
        properties={"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
    )
    validate_default_parameters_against_method_schema({}, schema)


@pytest.mark.unit
def test_raises_on_constraint_violation() -> None:
    schema = _schema(
        type="object",
        properties={
            "energy": {"type": "number", "minimum": 5, "unit": {"system": "udunits", "code": "keV"}}
        },
    )
    with pytest.raises(InvalidPlanDefaultParametersError) as exc_info:
        validate_default_parameters_against_method_schema({"energy": 1.0}, schema)
    assert "validation failed" in exc_info.value.reason


@pytest.mark.unit
def test_raises_on_type_mismatch() -> None:
    schema = _schema(
        type="object",
        properties={"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
    )
    with pytest.raises(InvalidPlanDefaultParametersError):
        validate_default_parameters_against_method_schema({"energy": "twelve"}, schema)


@pytest.mark.unit
def test_path_threading_in_error_message() -> None:
    """Error includes the offending key path so operators can fix
    the right key in a multi-key dict."""
    schema = _schema(
        type="object",
        properties={
            "energy": {
                "type": "number",
                "minimum": 5,
                "unit": {"system": "udunits", "code": "keV"},
            },
            "exposure": {
                "type": "integer",
                "minimum": 1,
                "unit": {"system": "udunits", "code": "ms"},
            },
        },
    )
    with pytest.raises(InvalidPlanDefaultParametersError) as exc_info:
        validate_default_parameters_against_method_schema({"energy": 12.0, "exposure": -5}, schema)
    assert "exposure" in exc_info.value.reason
