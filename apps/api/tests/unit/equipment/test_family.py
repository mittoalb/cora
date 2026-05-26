"""FamilyName VO + FamilyStatus enum tests."""

import pytest

from cora.equipment.aggregates.family import (
    FamilyName,
    FamilyStatus,
    InvalidFamilyNameError,
)

# ---------- FamilyName VO ----------


@pytest.mark.unit
def test_capability_name_accepts_normal_string() -> None:
    name = FamilyName("Continuous Rotation Tomography")
    assert name.value == "Continuous Rotation Tomography"


@pytest.mark.unit
def test_capability_name_trims_whitespace() -> None:
    name = FamilyName("  X-ray Fluorescence Mapping  ")
    assert name.value == "X-ray Fluorescence Mapping"


@pytest.mark.unit
def test_capability_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidFamilyNameError):
        FamilyName("")


@pytest.mark.unit
def test_capability_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidFamilyNameError):
        FamilyName("   \t\n   ")


@pytest.mark.unit
def test_capability_name_rejects_too_long() -> None:
    with pytest.raises(InvalidFamilyNameError):
        FamilyName("a" * 201)


@pytest.mark.unit
def test_capability_name_accepts_max_length() -> None:
    name = FamilyName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_capability_name_is_frozen() -> None:
    name = FamilyName("Tomography")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- FamilyStatus enum ----------


@pytest.mark.unit
def test_capability_status_has_all_three_lifecycle_values() -> None:
    """Pin the full status vocabulary from the BC map. Adding /
    removing values should be a deliberate change visible here."""
    assert {s.value for s in FamilyStatus} == {"Defined", "Versioned", "Deprecated"}


@pytest.mark.unit
def test_capability_status_values_are_pascal_case_strings() -> None:
    """Values match BC-map status vocabulary so log lines and DTOs
    read naturally without additional case conversion."""
    assert FamilyStatus.DEFINED == "Defined"
    assert FamilyStatus.VERSIONED == "Versioned"
    assert FamilyStatus.DEPRECATED == "Deprecated"


@pytest.mark.unit
def test_capability_status_is_str_enum_for_natural_serialization() -> None:
    """StrEnum so JSON serialization and string comparison Just Work
    without additional `.value` access."""
    assert isinstance(FamilyStatus.DEFINED, str)
    assert FamilyStatus.DEFINED == "Defined"
    assert f"{FamilyStatus.VERSIONED}" == "Versioned"


@pytest.mark.unit
def test_capability_status_can_be_constructed_from_string_value() -> None:
    """Round-trip: enum → string → enum. Future evolver bridges that
    read status from event payloads (for example, admin set-status backfill)
    will rely on this."""
    for status in FamilyStatus:
        assert FamilyStatus(status.value) == status
