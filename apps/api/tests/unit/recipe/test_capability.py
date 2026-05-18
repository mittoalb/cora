"""Unit tests for the Capability aggregate's state + VOs (Phase 6k)."""

from uuid import uuid4

import pytest

from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability import (
    CAPABILITY_CODE_MAX_LENGTH,
    CAPABILITY_DESCRIPTION_MAX_LENGTH,
    CAPABILITY_NAME_MAX_LENGTH,
    Capability,
    CapabilityCode,
    CapabilityName,
    CapabilityStatus,
    ExecutorShape,
    InvalidCapabilityCodeError,
    InvalidCapabilityDescriptionError,
    InvalidCapabilityNameError,
    InvalidExecutorShapesError,
    validate_capability_description,
    validate_executor_shapes,
)


@pytest.mark.unit
def test_capability_status_values() -> None:
    assert CapabilityStatus.DEFINED.value == "Defined"
    assert CapabilityStatus.VERSIONED.value == "Versioned"
    assert CapabilityStatus.DEPRECATED.value == "Deprecated"


@pytest.mark.unit
def test_executor_shape_closed_v1_values() -> None:
    """v1 ships exactly Method + Procedure; new shapes via rule-of-three trigger."""
    assert {s.value for s in ExecutorShape} == {"Method", "Procedure"}


@pytest.mark.unit
def test_capability_code_accepts_namespaced_value() -> None:
    code = CapabilityCode("cora.capability.flyscan")
    assert code.value == "cora.capability.flyscan"


@pytest.mark.unit
def test_capability_code_accepts_facility_extension() -> None:
    code = CapabilityCode("cora.capability.aps_2bm.flyscan")
    assert code.value == "cora.capability.aps_2bm.flyscan"


@pytest.mark.unit
def test_capability_code_trims_whitespace() -> None:
    code = CapabilityCode("  cora.capability.flyscan  ")
    assert code.value == "cora.capability.flyscan"


@pytest.mark.unit
def test_capability_code_rejects_empty() -> None:
    with pytest.raises(InvalidCapabilityCodeError) as exc:
        CapabilityCode("   ")
    assert "empty" in exc.value.reason


@pytest.mark.unit
def test_capability_code_rejects_missing_namespace() -> None:
    """Codes must start with `cora.capability.`."""
    with pytest.raises(InvalidCapabilityCodeError) as exc:
        CapabilityCode("flyscan")
    assert "cora.capability." in exc.value.reason


@pytest.mark.unit
def test_capability_code_rejects_namespace_with_no_suffix() -> None:
    """Pure-prefix codes (no segment after `cora.capability.`) are rejected."""
    with pytest.raises(InvalidCapabilityCodeError) as exc:
        CapabilityCode("cora.capability.")
    assert "no suffix" in exc.value.reason


@pytest.mark.unit
def test_capability_code_rejects_over_length() -> None:
    too_long = "cora.capability." + ("a" * CAPABILITY_CODE_MAX_LENGTH)
    with pytest.raises(InvalidCapabilityCodeError) as exc:
        CapabilityCode(too_long)
    assert "exceeds" in exc.value.reason


@pytest.mark.unit
def test_capability_name_trims_and_validates() -> None:
    name = CapabilityName("  FlyScan Tomography  ")
    assert name.value == "FlyScan Tomography"


@pytest.mark.unit
def test_capability_name_rejects_empty() -> None:
    with pytest.raises(InvalidCapabilityNameError):
        CapabilityName("   ")


@pytest.mark.unit
def test_capability_name_rejects_over_length() -> None:
    with pytest.raises(InvalidCapabilityNameError):
        CapabilityName("a" * (CAPABILITY_NAME_MAX_LENGTH + 1))


@pytest.mark.unit
def test_validate_capability_description_returns_none_for_none() -> None:
    assert validate_capability_description(None) is None


@pytest.mark.unit
def test_validate_capability_description_normalizes_empty_to_none() -> None:
    """Empty after trim is normalized to None (caller intent: no description)."""
    assert validate_capability_description("   ") is None


@pytest.mark.unit
def test_validate_capability_description_trims_present_value() -> None:
    assert validate_capability_description("  hello  ") == "hello"


@pytest.mark.unit
def test_validate_capability_description_rejects_over_length() -> None:
    with pytest.raises(InvalidCapabilityDescriptionError):
        validate_capability_description("a" * (CAPABILITY_DESCRIPTION_MAX_LENGTH + 1))


@pytest.mark.unit
def test_validate_executor_shapes_rejects_empty_set() -> None:
    """A Capability with no executor shapes has no operational meaning."""
    with pytest.raises(InvalidExecutorShapesError):
        validate_executor_shapes(frozenset())


@pytest.mark.unit
def test_validate_executor_shapes_returns_non_empty_set() -> None:
    out = validate_executor_shapes(frozenset({ExecutorShape.METHOD}))
    assert out == frozenset({ExecutorShape.METHOD})


@pytest.mark.unit
def test_capability_aggregate_required_fields_only() -> None:
    """A minimal Capability requires id + code + name; everything else defaults."""
    cap_id = uuid4()
    cap = Capability(
        id=cap_id,
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
    )
    assert cap.id == cap_id
    assert cap.status == CapabilityStatus.DEFINED
    assert cap.version is None
    assert cap.description is None
    assert cap.required_affordances == frozenset()
    assert cap.executor_shapes == frozenset()
    assert cap.parameter_schema is None
    assert cap.replaced_by_capability_id is None


@pytest.mark.unit
def test_capability_aggregate_with_full_declarative_contract() -> None:
    cap_id = uuid4()
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}
    cap = Capability(
        id=cap_id,
        code=CapabilityCode("cora.capability.flyscan"),
        name=CapabilityName("FlyScan"),
        description="Continuous-rotation tomography sweep.",
        required_affordances=frozenset({Affordance.ROTATABLE, Affordance.TRIGGERABLE}),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
        parameter_schema=schema,
    )
    assert cap.description == "Continuous-rotation tomography sweep."
    assert Affordance.ROTATABLE in cap.required_affordances
    assert cap.executor_shapes == frozenset({ExecutorShape.METHOD})
    assert cap.parameter_schema == schema
