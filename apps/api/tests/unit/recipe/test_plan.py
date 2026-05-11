"""PlanName VO + PlanStatus enum tests."""

import pytest

from cora.recipe.aggregates.plan import (
    InvalidPlanNameError,
    PlanName,
    PlanStatus,
)

# ---------- PlanName VO ----------


@pytest.mark.unit
def test_plan_name_accepts_normal_string() -> None:
    name = PlanName("32-ID XRF FlyScan with Eiger + SampleStage")
    assert name.value == "32-ID XRF FlyScan with Eiger + SampleStage"


@pytest.mark.unit
def test_plan_name_trims_whitespace() -> None:
    name = PlanName("  32-ID XRF FlyScan  ")
    assert name.value == "32-ID XRF FlyScan"


@pytest.mark.unit
def test_plan_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidPlanNameError):
        PlanName("")


@pytest.mark.unit
def test_plan_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidPlanNameError):
        PlanName("   \t\n   ")


@pytest.mark.unit
def test_plan_name_rejects_too_long() -> None:
    with pytest.raises(InvalidPlanNameError):
        PlanName("a" * 201)


@pytest.mark.unit
def test_plan_name_accepts_max_length() -> None:
    name = PlanName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_plan_name_is_frozen() -> None:
    name = PlanName("Standard FlyScan Plan")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


@pytest.mark.unit
def test_plan_name_uses_shared_validate_name_helper() -> None:
    """Pin: PlanName is the 10th VO; it routes through the shared
    `cora.infrastructure.name.validate_name` helper hoisted in 6e-1.
    A direct import test ensures we don't accidentally re-add the
    duplicated trim logic later."""
    import inspect

    from cora.recipe.aggregates.plan import state as plan_state

    src = inspect.getsource(PlanName.__post_init__)
    assert "validate_name" in src
    assert "validate_name" in plan_state.__dict__ or any(
        "validate_name" in str(v) for v in plan_state.__dict__.values()
    )


# ---------- PlanStatus enum ----------


@pytest.mark.unit
def test_plan_status_has_all_three_lifecycle_values() -> None:
    """Mirrors Method / Practice / Capability lifecycle vocabulary
    (gate-review Q2: structural lifecycle only; approval lives in
    Decision BC)."""
    assert {s.value for s in PlanStatus} == {"Defined", "Versioned", "Deprecated"}


@pytest.mark.unit
def test_plan_status_values_are_pascal_case_strings() -> None:
    assert PlanStatus.DEFINED == "Defined"
    assert PlanStatus.VERSIONED == "Versioned"
    assert PlanStatus.DEPRECATED == "Deprecated"


@pytest.mark.unit
def test_plan_status_is_str_enum_for_natural_serialization() -> None:
    assert isinstance(PlanStatus.DEFINED, str)
    assert PlanStatus.DEFINED == "Defined"
    assert f"{PlanStatus.VERSIONED}" == "Versioned"


@pytest.mark.unit
def test_plan_status_can_be_constructed_from_string_value() -> None:
    for status in PlanStatus:
        assert PlanStatus(status.value) == status
