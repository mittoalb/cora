"""AssetName VO + AssetLevel + AssetLifecycle enum tests."""

import pytest

from cora.equipment.aggregates.asset import (
    AssetLevel,
    AssetLifecycle,
    AssetName,
    InvalidAssetNameError,
)

# ---------- AssetName VO ----------


@pytest.mark.unit
def test_asset_name_accepts_normal_string() -> None:
    name = AssetName("APS-2BM-A")
    assert name.value == "APS-2BM-A"


@pytest.mark.unit
def test_asset_name_trims_whitespace() -> None:
    name = AssetName("  Eiger-2X-9M  ")
    assert name.value == "Eiger-2X-9M"


@pytest.mark.unit
def test_asset_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidAssetNameError):
        AssetName("")


@pytest.mark.unit
def test_asset_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidAssetNameError):
        AssetName("   \t\n   ")


@pytest.mark.unit
def test_asset_name_rejects_too_long() -> None:
    with pytest.raises(InvalidAssetNameError):
        AssetName("a" * 201)


@pytest.mark.unit
def test_asset_name_accepts_max_length() -> None:
    name = AssetName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_asset_name_is_frozen() -> None:
    name = AssetName("APS-2BM")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- AssetLevel enum ----------


@pytest.mark.unit
def test_asset_level_has_all_six_isa88_levels() -> None:
    """Pin the full level vocabulary from the BC map (ISA-88-derived,
    single-word convention). Adding / removing values should be a
    deliberate change visible here."""
    assert {lvl.value for lvl in AssetLevel} == {
        "Enterprise",
        "Site",
        "Area",
        "Unit",
        "Assembly",
        "Device",
    }


@pytest.mark.unit
def test_asset_level_values_are_pascal_case_strings() -> None:
    assert AssetLevel.ENTERPRISE == "Enterprise"
    assert AssetLevel.SITE == "Site"
    assert AssetLevel.AREA == "Area"
    assert AssetLevel.UNIT == "Unit"
    assert AssetLevel.ASSEMBLY == "Assembly"
    assert AssetLevel.DEVICE == "Device"


@pytest.mark.unit
def test_asset_level_is_str_enum_for_natural_serialization() -> None:
    """StrEnum so JSON serialization and string comparison Just Work
    without `.value` access. AssetLevel is carried in event payloads
    as the StrEnum's string value, so this matters for the wire
    format."""
    assert isinstance(AssetLevel.ENTERPRISE, str)
    assert AssetLevel.ENTERPRISE == "Enterprise"
    assert f"{AssetLevel.SITE}" == "Site"


@pytest.mark.unit
def test_asset_level_can_be_constructed_from_string_value() -> None:
    """The evolver reconstructs the enum from event payload strings via
    `AssetLevel(payload['level'])`. Pin that the round-trip works
    for every value."""
    for level in AssetLevel:
        assert AssetLevel(level.value) == level


# ---------- AssetLifecycle enum ----------


@pytest.mark.unit
def test_asset_lifecycle_has_all_four_lifecycle_values() -> None:
    """Pin the full lifecycle vocabulary from the BC map. Adding /
    removing values should be a deliberate change visible here."""
    assert {lc.value for lc in AssetLifecycle} == {
        "Commissioned",
        "Active",
        "Maintenance",
        "Decommissioned",
    }


@pytest.mark.unit
def test_asset_lifecycle_values_are_pascal_case_strings() -> None:
    assert AssetLifecycle.COMMISSIONED == "Commissioned"
    assert AssetLifecycle.ACTIVE == "Active"
    assert AssetLifecycle.MAINTENANCE == "Maintenance"
    assert AssetLifecycle.DECOMMISSIONED == "Decommissioned"


@pytest.mark.unit
def test_asset_lifecycle_is_str_enum() -> None:
    assert isinstance(AssetLifecycle.COMMISSIONED, str)
    assert AssetLifecycle.COMMISSIONED == "Commissioned"
