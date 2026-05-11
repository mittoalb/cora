"""MethodName VO + MethodStatus enum tests."""

import pytest

from cora.recipe.aggregates.method import (
    InvalidMethodNameError,
    MethodName,
    MethodStatus,
)

# ---------- MethodName VO ----------


@pytest.mark.unit
def test_method_name_accepts_normal_string() -> None:
    name = MethodName("X-ray Fluorescence Mapping")
    assert name.value == "X-ray Fluorescence Mapping"


@pytest.mark.unit
def test_method_name_trims_whitespace() -> None:
    name = MethodName("  Step Tomography  ")
    assert name.value == "Step Tomography"


@pytest.mark.unit
def test_method_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidMethodNameError):
        MethodName("")


@pytest.mark.unit
def test_method_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidMethodNameError):
        MethodName("   \t\n   ")


@pytest.mark.unit
def test_method_name_rejects_too_long() -> None:
    with pytest.raises(InvalidMethodNameError):
        MethodName("a" * 201)


@pytest.mark.unit
def test_method_name_accepts_max_length() -> None:
    name = MethodName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_method_name_is_frozen() -> None:
    name = MethodName("Tomography")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- MethodStatus enum ----------


@pytest.mark.unit
def test_method_status_has_all_three_lifecycle_values() -> None:
    """Pin the full status vocabulary from the BC map. Adding /
    removing values should be a deliberate change visible here."""
    assert {s.value for s in MethodStatus} == {"Defined", "Versioned", "Deprecated"}


@pytest.mark.unit
def test_method_status_values_are_pascal_case_strings() -> None:
    assert MethodStatus.DEFINED == "Defined"
    assert MethodStatus.VERSIONED == "Versioned"
    assert MethodStatus.DEPRECATED == "Deprecated"


@pytest.mark.unit
def test_method_status_is_str_enum_for_natural_serialization() -> None:
    assert isinstance(MethodStatus.DEFINED, str)
    assert MethodStatus.DEFINED == "Defined"
    assert f"{MethodStatus.VERSIONED}" == "Versioned"


@pytest.mark.unit
def test_method_status_can_be_constructed_from_string_value() -> None:
    for status in MethodStatus:
        assert MethodStatus(status.value) == status
