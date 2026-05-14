"""Unit tests for the Run effective_parameters validator (Phase 6g-c).

Mirrors `tests/unit/recipe/test_plan_parameters_validation.py`
(6g-b) case for case so the two BC wrappers stay aligned.
Validates dicts against a Method's parameters_schema using
jsonschema-rs. STRICT when the schema is None — non-empty
effective_parameters without a declared schema raise
InvalidRunParametersError (post-6g audit reversal; see
[[project_run_parameters_design]] §audit-correction).
"""

from typing import Any

import pytest

from cora.run.aggregates.run import (
    InvalidRunParametersError,
    validate_effective_parameters_against_method_schema,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(**body: Any) -> dict[str, Any]:
    return {"$schema": _DRAFT, **body}


@pytest.mark.unit
def test_passes_when_schema_is_none_and_effective_is_empty() -> None:
    validate_effective_parameters_against_method_schema({}, None)


@pytest.mark.unit
def test_raises_when_schema_is_none_and_effective_is_non_empty() -> None:
    """Strict (post-6g audit reversal): Method declares no contract
    AND effective_parameters supplied -> reject. Operator must declare
    schema (an empty `{}` works) or omit overrides AND clear Plan
    defaults. Aligns with 5g-c's strict zero-Capabilities posture."""
    with pytest.raises(InvalidRunParametersError) as exc_info:
        validate_effective_parameters_against_method_schema({"anything": 42}, None)
    assert "Method declares no parameters_schema" in exc_info.value.reason
    assert "'anything'" in exc_info.value.reason


@pytest.mark.unit
def test_passes_when_effective_matches_schema() -> None:
    schema = _schema(
        type="object",
        properties={"energy_kev": {"type": "number", "minimum": 5, "maximum": 50}},
    )
    validate_effective_parameters_against_method_schema({"energy_kev": 12.0}, schema)


@pytest.mark.unit
def test_passes_when_effective_is_empty_even_with_schema() -> None:
    """Empty effective satisfies any schema at this layer."""
    schema = _schema(
        type="object",
        required=["energy_kev"],
        properties={"energy_kev": {"type": "number"}},
    )
    validate_effective_parameters_against_method_schema({}, schema)


@pytest.mark.unit
def test_raises_on_constraint_violation() -> None:
    schema = _schema(
        type="object",
        properties={"energy_kev": {"type": "number", "minimum": 5}},
    )
    with pytest.raises(InvalidRunParametersError) as exc_info:
        validate_effective_parameters_against_method_schema({"energy_kev": 1.0}, schema)
    assert "validation failed" in exc_info.value.reason


@pytest.mark.unit
def test_raises_on_type_mismatch() -> None:
    schema = _schema(
        type="object",
        properties={"energy_kev": {"type": "number"}},
    )
    with pytest.raises(InvalidRunParametersError):
        validate_effective_parameters_against_method_schema({"energy_kev": "twelve"}, schema)


@pytest.mark.unit
def test_path_threading_in_error_message() -> None:
    schema = _schema(
        type="object",
        properties={
            "energy_kev": {"type": "number", "minimum": 5},
            "exposure_ms": {"type": "integer", "minimum": 1},
        },
    )
    with pytest.raises(InvalidRunParametersError) as exc_info:
        validate_effective_parameters_against_method_schema(
            {"energy_kev": 12.0, "exposure_ms": -5}, schema
        )
    assert "exposure_ms" in exc_info.value.reason
