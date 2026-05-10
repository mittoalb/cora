"""ZoneName value-object validation."""

import pytest

from cora.trust.aggregates.zone import InvalidZoneNameError, ZoneName


@pytest.mark.unit
def test_zone_name_accepts_normal_string() -> None:
    name = ZoneName("Detector")
    assert name.value == "Detector"


@pytest.mark.unit
def test_zone_name_trims_whitespace() -> None:
    name = ZoneName("  Detector  ")
    assert name.value == "Detector"


@pytest.mark.unit
def test_zone_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidZoneNameError):
        ZoneName("")


@pytest.mark.unit
def test_zone_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidZoneNameError):
        ZoneName("   \t\n   ")


@pytest.mark.unit
def test_zone_name_rejects_too_long() -> None:
    with pytest.raises(InvalidZoneNameError):
        ZoneName("a" * 201)


@pytest.mark.unit
def test_zone_name_accepts_max_length() -> None:
    name = ZoneName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_zone_name_is_frozen() -> None:
    name = ZoneName("Detector")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]
