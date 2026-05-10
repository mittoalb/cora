"""SubjectName VO + SubjectStatus enum tests."""

import pytest

from cora.subject.aggregates.subject import (
    InvalidSubjectNameError,
    SubjectName,
    SubjectStatus,
)

# ---------- SubjectName VO ----------


@pytest.mark.unit
def test_subject_name_accepts_normal_string() -> None:
    name = SubjectName("Sample-A1")
    assert name.value == "Sample-A1"


@pytest.mark.unit
def test_subject_name_trims_whitespace() -> None:
    name = SubjectName("  Sample-A1  ")
    assert name.value == "Sample-A1"


@pytest.mark.unit
def test_subject_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidSubjectNameError):
        SubjectName("")


@pytest.mark.unit
def test_subject_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidSubjectNameError):
        SubjectName("   \t\n   ")


@pytest.mark.unit
def test_subject_name_rejects_too_long() -> None:
    with pytest.raises(InvalidSubjectNameError):
        SubjectName("a" * 201)


@pytest.mark.unit
def test_subject_name_accepts_max_length() -> None:
    name = SubjectName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_subject_name_is_frozen() -> None:
    name = SubjectName("Sample-A1")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- SubjectStatus enum ----------


@pytest.mark.unit
def test_subject_status_has_all_seven_lifecycle_values() -> None:
    """Pin the full status vocabulary from the BC map. Adding /
    removing values should be a deliberate change visible here."""
    assert {s.value for s in SubjectStatus} == {
        "Received",
        "Mounted",
        "Measured",
        "Removed",
        "Returned",
        "Stored",
        "Discarded",
    }


@pytest.mark.unit
def test_subject_status_values_are_pascal_case_strings() -> None:
    """Values match BC-map status vocabulary so log lines and DTOs
    read naturally without additional case conversion."""
    assert SubjectStatus.RECEIVED == "Received"
    assert SubjectStatus.MOUNTED == "Mounted"
    assert SubjectStatus.MEASURED == "Measured"
    assert SubjectStatus.REMOVED == "Removed"
    assert SubjectStatus.RETURNED == "Returned"
    assert SubjectStatus.STORED == "Stored"
    assert SubjectStatus.DISCARDED == "Discarded"


@pytest.mark.unit
def test_subject_status_is_str_enum_for_natural_serialization() -> None:
    """StrEnum so JSON serialization and string comparison Just Work
    without additional `.value` access. Pin so a future change to a
    plain Enum (which would break event payload serialization) is
    deliberate."""
    assert isinstance(SubjectStatus.RECEIVED, str)
    assert SubjectStatus.RECEIVED == "Received"
    assert f"{SubjectStatus.MOUNTED}" == "Mounted"


@pytest.mark.unit
def test_subject_status_can_be_constructed_from_string_value() -> None:
    """The evolver bridge (4b+) reconstructs the enum from event
    payload strings via `SubjectStatus(payload["status"])`. Pin
    that the round-trip works for every value."""
    for status in SubjectStatus:
        assert SubjectStatus(status.value) == status
