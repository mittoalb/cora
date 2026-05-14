"""Unit tests for the Asset.settings cross-Capability validator (Phase 5g-c).

Two pieces:
  - merge_patch: RFC 7396 JSON Merge Patch semantics (recursive,
    null-deletes, absent-key-preserves)
  - validate_settings_against_capabilities: union schemas + strict /
    permissive mode + true-type-conflict detection
"""

from typing import Any
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset.settings_validation import (
    merge_patch,
    validate_settings_against_capabilities,
)
from cora.equipment.aggregates.asset.state import InvalidAssetSettingsError
from cora.equipment.aggregates.capability.state import (
    Capability,
    CapabilityName,
    CapabilityStatus,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _capability(*, settings_schema: dict[str, Any] | None) -> Capability:
    return Capability(
        id=uuid4(),
        name=CapabilityName("Tomography"),
        status=CapabilityStatus.DEFINED,
        settings_schema=settings_schema,
    )


def _schema(**body: Any) -> dict[str, Any]:
    return {"$schema": _DRAFT, **body}


# ---------- merge_patch (RFC 7396) ----------


@pytest.mark.unit
def test_merge_patch_sets_new_key() -> None:
    assert merge_patch({}, {"a": 1}) == {"a": 1}


@pytest.mark.unit
def test_merge_patch_replaces_existing_key() -> None:
    assert merge_patch({"a": 1}, {"a": 2}) == {"a": 2}


@pytest.mark.unit
def test_merge_patch_null_deletes_existing_key() -> None:
    assert merge_patch({"a": 1, "b": 2}, {"a": None}) == {"b": 2}


@pytest.mark.unit
def test_merge_patch_null_on_absent_key_is_no_op() -> None:
    assert merge_patch({"a": 1}, {"b": None}) == {"a": 1}


@pytest.mark.unit
def test_merge_patch_preserves_absent_keys() -> None:
    assert merge_patch({"a": 1, "b": 2}, {"a": 5}) == {"a": 5, "b": 2}


@pytest.mark.unit
def test_merge_patch_recurses_into_nested_dicts() -> None:
    assert merge_patch({"a": {"x": 1, "y": 2}}, {"a": {"y": 5}}) == {"a": {"x": 1, "y": 5}}


@pytest.mark.unit
def test_merge_patch_null_inside_nested_dict_deletes_nested_key() -> None:
    assert merge_patch({"a": {"x": 1, "y": 2}}, {"a": {"y": None}}) == {"a": {"x": 1}}


@pytest.mark.unit
def test_merge_patch_returns_new_dict_does_not_mutate_input() -> None:
    current = {"a": 1}
    patch = {"b": 2}
    result = merge_patch(current, patch)
    assert current == {"a": 1}
    assert patch == {"b": 2}
    assert result == {"a": 1, "b": 2}


@pytest.mark.unit
def test_merge_patch_replaces_dict_with_scalar() -> None:
    """Patching a dict-typed key with a scalar replaces (not merges)."""
    assert merge_patch({"a": {"x": 1}}, {"a": 42}) == {"a": 42}


@pytest.mark.unit
def test_merge_patch_does_not_alias_nested_dicts_from_current() -> None:
    """Pinned: the result must be deeply independent of `current`.
    Mutating a nested dict in the returned result must NOT propagate
    back into `current`. Pre-fix the implementation passed nested
    dicts by reference (shallow copy at top level only), which would
    let event-payload mutations corrupt prior Asset state across
    folds."""
    current: dict[str, Any] = {"a": {"x": 1, "y": 2}, "b": "scalar"}
    patch: dict[str, Any] = {"c": 3}  # patch doesn't touch `a`
    result = merge_patch(current, patch)
    # Mutate the nested dict in the result.
    result["a"]["x"] = 999
    # `current` must NOT see the mutation.
    assert current["a"]["x"] == 1


@pytest.mark.unit
def test_merge_patch_does_not_alias_nested_dicts_from_patch() -> None:
    """Symmetric pin: mutating a nested dict in the returned result
    must NOT propagate back into `patch` either."""
    current: dict[str, Any] = {}
    patch = {"a": {"x": 1}}
    result = merge_patch(current, patch)
    result["a"]["x"] = 999
    assert patch["a"]["x"] == 1


# ---------- validate_settings_against_capabilities ----------


@pytest.mark.unit
def test_validate_no_capabilities_no_settings_passes() -> None:
    """Trivial case: nothing to validate against, nothing to validate."""
    validate_settings_against_capabilities({}, [])


@pytest.mark.unit
def test_validate_no_capabilities_non_empty_settings_rejects() -> None:
    """Asset with no Capabilities cannot have settings (no schema source)."""
    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        validate_settings_against_capabilities({"x": 1}, [])
    assert "no assigned Capabilities" in exc_info.value.reason


@pytest.mark.unit
def test_validate_passes_when_all_keys_match_single_schema() -> None:
    cap = _capability(
        settings_schema=_schema(
            type="object",
            properties={"energy_kev": {"type": "number", "minimum": 5}},
        )
    )
    validate_settings_against_capabilities({"energy_kev": 30}, [cap])


@pytest.mark.unit
def test_validate_rejects_constraint_violation() -> None:
    cap = _capability(
        settings_schema=_schema(
            type="object",
            properties={"energy_kev": {"type": "number", "minimum": 5}},
        )
    )
    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        validate_settings_against_capabilities({"energy_kev": 1}, [cap])
    assert "energy_kev" in exc_info.value.reason


@pytest.mark.unit
def test_validate_rejects_orphan_key_when_all_capabilities_have_schemas() -> None:
    """STRICT mode: if every Capability declares a schema, unknown keys reject."""
    cap = _capability(
        settings_schema=_schema(
            type="object",
            properties={"energy_kev": {"type": "number"}},
        )
    )
    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        validate_settings_against_capabilities({"energy_kev": 30, "unknown_key": "x"}, [cap])
    assert "unknown_key" in exc_info.value.reason


@pytest.mark.unit
def test_validate_tolerates_unknown_key_when_one_capability_is_schemaless() -> None:
    """PERMISSIVE mode: a single schemaless Capability widens the union to
    accept unknown keys (5g-a 'degrade gracefully' stance).
    """
    declared = _capability(
        settings_schema=_schema(
            type="object",
            properties={"energy_kev": {"type": "number"}},
        )
    )
    schemaless = _capability(settings_schema=None)
    validate_settings_against_capabilities(
        {"energy_kev": 30, "vendor_specific": "x"},
        [declared, schemaless],
    )


@pytest.mark.unit
def test_validate_unions_keys_across_two_capabilities() -> None:
    cap_a = _capability(
        settings_schema=_schema(type="object", properties={"x": {"type": "number"}})
    )
    cap_b = _capability(
        settings_schema=_schema(type="object", properties={"y": {"type": "string"}})
    )
    validate_settings_against_capabilities({"x": 1, "y": "ok"}, [cap_a, cap_b])


@pytest.mark.unit
def test_validate_intersects_constraints_for_shared_key() -> None:
    """Two Capabilities both declare `temperature_c` as number with
    different minimums; allOf intersection makes the higher minimum
    binding."""
    cap_a = _capability(
        settings_schema=_schema(
            type="object",
            properties={"temperature_c": {"type": "number", "minimum": 5}},
        )
    )
    cap_b = _capability(
        settings_schema=_schema(
            type="object",
            properties={"temperature_c": {"type": "number", "minimum": 20}},
        )
    )
    # 25 satisfies both
    validate_settings_against_capabilities({"temperature_c": 25}, [cap_a, cap_b])
    # 10 satisfies cap_a but not cap_b -> reject
    with pytest.raises(InvalidAssetSettingsError):
        validate_settings_against_capabilities({"temperature_c": 10}, [cap_a, cap_b])


@pytest.mark.unit
def test_validate_rejects_true_type_conflict_across_capabilities() -> None:
    """Two Capabilities declare the same key with incompatible types —
    no value can satisfy both; the validator names both Capabilities."""
    cap_a = _capability(
        settings_schema=_schema(
            type="object",
            properties={"temperature_c": {"type": "number"}},
        )
    )
    cap_b = _capability(
        settings_schema=_schema(
            type="object",
            properties={"temperature_c": {"type": "string"}},
        )
    )
    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        validate_settings_against_capabilities({"temperature_c": 25}, [cap_a, cap_b])
    assert "incompatible types" in exc_info.value.reason
    assert "temperature_c" in exc_info.value.reason
    # Both Capability ids surface in the diagnostic.
    assert str(cap_a.id) in exc_info.value.reason
    assert str(cap_b.id) in exc_info.value.reason


@pytest.mark.unit
def test_validate_empty_settings_passes_with_strict_schemas() -> None:
    """Removing all settings (empty dict) is always valid: no value is
    constrained because none is provided. Useful for the 'reset to
    defaults' cleanup path via merge_patch with all-null."""
    cap = _capability(
        settings_schema=_schema(
            type="object",
            properties={"energy_kev": {"type": "number", "minimum": 5}},
            required=[],  # leave required empty so empty dict passes
        )
    )
    validate_settings_against_capabilities({}, [cap])
