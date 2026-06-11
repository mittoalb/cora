"""Unit tests for ClearanceTemplate aggregate state, VOs, and enums."""

import pytest

from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateCode,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
    InvalidClearanceTemplateCodeError,
    InvalidClearanceTemplateTitleError,
    InvalidClearanceTemplateVersionError,
    clearance_template_stream_id,
)
from cora.shared.facility_code import FacilityCode

# ---------- ClearanceTemplateStatus enum ----------


@pytest.mark.unit
def test_clearance_template_status_has_all_four_lifecycle_values() -> None:
    """Pin the full status vocabulary from the design. Adding / removing
    values should be a deliberate change visible here."""
    assert {s.value for s in ClearanceTemplateStatus} == {
        "Draft",
        "Active",
        "Deprecated",
        "Withdrawn",
    }


@pytest.mark.unit
def test_clearance_template_status_values_are_pascal_case_strings() -> None:
    """Values match the BC-map status vocabulary so log lines and DTOs
    read naturally without additional case conversion."""
    assert ClearanceTemplateStatus.DRAFT == "Draft"
    assert ClearanceTemplateStatus.ACTIVE == "Active"
    assert ClearanceTemplateStatus.DEPRECATED == "Deprecated"
    assert ClearanceTemplateStatus.WITHDRAWN == "Withdrawn"


@pytest.mark.unit
def test_clearance_template_status_is_str_enum() -> None:
    """StrEnum so JSON serialization and string comparison Just Work."""
    assert isinstance(ClearanceTemplateStatus.DRAFT, str)
    assert ClearanceTemplateStatus.DRAFT == "Draft"
    assert f"{ClearanceTemplateStatus.ACTIVE}" == "Active"


# ---------- ClearanceTemplateCode VO ----------


@pytest.mark.unit
def test_clearance_template_code_accepts_normal_string() -> None:
    code = ClearanceTemplateCode("ESAF-v1")
    assert code.value == "ESAF-v1"


@pytest.mark.unit
def test_clearance_template_code_trims_whitespace() -> None:
    code = ClearanceTemplateCode("  SAF-screening  ")
    assert code.value == "SAF-screening"


@pytest.mark.unit
def test_clearance_template_code_rejects_empty_string() -> None:
    with pytest.raises(InvalidClearanceTemplateCodeError):
        ClearanceTemplateCode("")


@pytest.mark.unit
def test_clearance_template_code_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidClearanceTemplateCodeError):
        ClearanceTemplateCode("   \t\n   ")


@pytest.mark.unit
def test_clearance_template_code_rejects_too_long() -> None:
    with pytest.raises(InvalidClearanceTemplateCodeError):
        ClearanceTemplateCode("a" * 101)


@pytest.mark.unit
def test_clearance_template_code_accepts_max_length() -> None:
    code = ClearanceTemplateCode("a" * 50)
    assert len(code.value) == 50


# ---------- ClearanceTemplateTitle VO ----------


@pytest.mark.unit
def test_clearance_template_title_accepts_normal_string() -> None:
    title = ClearanceTemplateTitle("Experiment Safety Assessment Form")
    assert title.value == "Experiment Safety Assessment Form"


@pytest.mark.unit
def test_clearance_template_title_trims_whitespace() -> None:
    title = ClearanceTemplateTitle("  Beamline Safety Form  ")
    assert title.value == "Beamline Safety Form"


@pytest.mark.unit
def test_clearance_template_title_rejects_empty_string() -> None:
    with pytest.raises(InvalidClearanceTemplateTitleError):
        ClearanceTemplateTitle("")


@pytest.mark.unit
def test_clearance_template_title_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidClearanceTemplateTitleError):
        ClearanceTemplateTitle("   \t\n   ")


@pytest.mark.unit
def test_clearance_template_title_rejects_too_long() -> None:
    with pytest.raises(InvalidClearanceTemplateTitleError):
        ClearanceTemplateTitle("a" * 256)


@pytest.mark.unit
def test_clearance_template_title_accepts_max_length() -> None:
    title = ClearanceTemplateTitle("a" * 200)
    assert len(title.value) == 200


# ---------- ClearanceTemplateVersion VO ----------


@pytest.mark.unit
def test_clearance_template_version_accepts_positive_integer() -> None:
    version = ClearanceTemplateVersion(1)
    assert version.value == 1


@pytest.mark.unit
def test_clearance_template_version_accepts_higher_versions() -> None:
    version = ClearanceTemplateVersion(42)
    assert version.value == 42


@pytest.mark.unit
def test_clearance_template_version_rejects_zero() -> None:
    with pytest.raises(InvalidClearanceTemplateVersionError):
        ClearanceTemplateVersion(0)


@pytest.mark.unit
def test_clearance_template_version_rejects_negative() -> None:
    with pytest.raises(InvalidClearanceTemplateVersionError):
        ClearanceTemplateVersion(-1)


# ---------- clearance_template_stream_id ----------


@pytest.mark.unit
def test_clearance_template_stream_id_is_deterministic_for_same_inputs() -> None:
    """Same facility_code + template_code -> same stream_id."""
    facility_code = FacilityCode("aps").value
    template_code = "ESAF-v1"
    a = clearance_template_stream_id(facility_code, template_code)
    b = clearance_template_stream_id(facility_code, template_code)
    assert a == b


@pytest.mark.unit
def test_clearance_template_stream_id_differs_for_different_facility_codes() -> None:
    """Different facility_code -> different stream_id, even with same template_code."""
    template_code = "ESAF-v1"
    a = clearance_template_stream_id(FacilityCode("aps").value, template_code)
    b = clearance_template_stream_id(FacilityCode("maxiv").value, template_code)
    assert a != b


@pytest.mark.unit
def test_clearance_template_stream_id_differs_for_different_template_codes() -> None:
    """Different template_code -> different stream_id, even with same facility_code."""
    facility_code = FacilityCode("aps").value
    a = clearance_template_stream_id(facility_code, "ESAF-v1")
    b = clearance_template_stream_id(facility_code, "ESAF-v2")
    assert a != b
