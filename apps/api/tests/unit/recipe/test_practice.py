"""PracticeName VO + PracticeStatus enum tests."""

import pytest

from cora.recipe.aggregates.practice import (
    InvalidPracticeNameError,
    PracticeName,
    PracticeStatus,
)

# ---------- PracticeName VO ----------


@pytest.mark.unit
def test_practice_name_accepts_normal_string() -> None:
    name = PracticeName("APS Sector 2 XRF Fly Mapping")
    assert name.value == "APS Sector 2 XRF Fly Mapping"


@pytest.mark.unit
def test_practice_name_trims_whitespace() -> None:
    name = PracticeName("  APS Standard Tomography  ")
    assert name.value == "APS Standard Tomography"


@pytest.mark.unit
def test_practice_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidPracticeNameError):
        PracticeName("")


@pytest.mark.unit
def test_practice_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidPracticeNameError):
        PracticeName("   \t\n   ")


@pytest.mark.unit
def test_practice_name_rejects_too_long() -> None:
    with pytest.raises(InvalidPracticeNameError):
        PracticeName("a" * 201)


@pytest.mark.unit
def test_practice_name_accepts_max_length() -> None:
    name = PracticeName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_practice_name_is_frozen() -> None:
    name = PracticeName("Standard XRF")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- PracticeStatus enum ----------


@pytest.mark.unit
def test_practice_status_has_all_three_lifecycle_values() -> None:
    """Mirrors Method / Family lifecycle vocabulary."""
    assert {s.value for s in PracticeStatus} == {"Defined", "Versioned", "Deprecated"}


@pytest.mark.unit
def test_practice_status_values_are_pascal_case_strings() -> None:
    assert PracticeStatus.DEFINED == "Defined"
    assert PracticeStatus.VERSIONED == "Versioned"
    assert PracticeStatus.DEPRECATED == "Deprecated"


@pytest.mark.unit
def test_practice_status_is_str_enum_for_natural_serialization() -> None:
    assert isinstance(PracticeStatus.DEFINED, str)
    assert PracticeStatus.DEFINED == "Defined"
    assert f"{PracticeStatus.VERSIONED}" == "Versioned"


@pytest.mark.unit
def test_practice_status_can_be_constructed_from_string_value() -> None:
    for status in PracticeStatus:
        assert PracticeStatus(status.value) == status
