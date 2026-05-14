"""Cross-Capability validation for Asset.settings (Phase 5g-c).

Two pieces:

  - `merge_patch(current, patch)`: apply RFC 7396 (JSON Merge Patch)
    semantics. Keys with non-null values are set/replaced; keys with
    null are deleted; absent keys are preserved.

  - `validate_settings_against_capabilities(settings, capabilities)`:
    union all assigned Capabilities' settings_schemas (5g-a) and
    validate the proposed settings dict against the union via
    `jsonschema-rs`. Raises `InvalidAssetSettingsError(reason)` on
    failure with a clear diagnostic.

## Union semantics

For each currently-assigned Capability with a non-None
`settings_schema`:
  - Every property name declared in any Capability's `properties`
    is allowed.
  - For properties declared in MULTIPLE Capabilities, all
    constraints intersect via `allOf`-style semantics
    (`jsonschema-rs` handles this natively when given an
    `allOf` array): `minimum` takes the highest, `maximum` takes
    the lowest, `type` must agree across all declarations.

The implementation builds a single mega-schema with `allOf: [...]`
(one entry per Capability with a schema) PLUS an `unevaluatedProperties:
false` clause WHEN every assigned Capability has declared a schema
(strict mode). If at least one assigned Capability is schemaless,
we skip the strict clause (permissive mode); unknown keys are
tolerated. This preserves 5g-a's "degrade gracefully" stance.

## Schemaless-Capability tolerance + zero-Capabilities edge case

A Capability with `settings_schema=None` does not contribute to the
union. Three modes follow:

  - **STRICT**: every assigned Capability declares a schema (no
    schemaless Capabilities). The validator rejects orphan keys
    (`additionalProperties: false`).
  - **PERMISSIVE**: at least one assigned Capability is schemaless,
    AND at least one declares a schema. Unknown keys are tolerated
    (`degrade gracefully`); declared keys still validate.
  - **NO-CAPABILITIES**: the Asset has zero assigned Capabilities.
    Empty settings is trivially valid; non-empty settings is
    rejected (no schema source). This is hard-strict: an Asset with
    no Capabilities has no claim to any settings.

The asymmetry between PERMISSIVE (>=1 schemaless cap allows
anything) and NO-CAPABILITIES (zero caps allows nothing) is
deliberate: a schemaless cap is an explicit "this Capability
exists but its schema isn't declared yet"; zero caps is "this Asset
shouldn't have settings at all".

## Error shape

`InvalidAssetSettingsError` carries a `reason` string with enough
detail for an operator to fix the patch:
  - "key 'energy_kev' is not declared by any assigned Capability's
    settings_schema" (orphan)
  - "value <X> for key 'energy_kev' violates schema constraint
    <details>" (constraint violation)
  - "key 'temperature_c' has incompatible types across Capabilities
    (Capability A: number, Capability B: string)" (true conflict)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import copy
from collections.abc import Mapping, Sequence
from typing import Any

import jsonschema_rs

from cora.equipment.aggregates.asset.state import InvalidAssetSettingsError
from cora.equipment.aggregates.capability.state import Capability
from cora.infrastructure.json_schema_subset import DRAFT_2020_12_URI


def merge_patch(current: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    """Apply RFC 7396 JSON Merge Patch semantics.

    Returns a NEW deeply-copied dict (does not alias `current` at any
    nesting depth):
      - keys in `patch` with non-null values: set / replace
      - keys in `patch` with null: deleted from result
      - keys absent from `patch`: preserved from `current`

    Recursive on nested dicts: `merge_patch({"a": {"b": 1}}, {"a":
    {"c": 2}}) == {"a": {"b": 1, "c": 2}}`. RFC 7396 says nested
    null also deletes (`merge_patch({"a": {"b": 1}}, {"a": {"b":
    null}}) == {"a": {}}`).

    The result is `copy.deepcopy`'d so caller mutations of the
    returned dict do not propagate into `current` (the prior
    `Asset.settings`) or into the event payload that this dict
    becomes. Settings dicts are typically small (5-30 keys), so
    deepcopy cost is negligible compared to the safety guarantee.

    Note: cannot represent "set key to null" — null is overloaded as
    the delete sentinel. Settings values in CORA are never null in
    practice (use absence or a typed sentinel).
    """
    result: dict[str, Any] = copy.deepcopy(dict(current))
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            # Recursive merge into existing nested dict
            result[key] = merge_patch(result[key], value)
        else:
            # Set / replace (including dict-into-non-dict and scalars).
            # Deep-copy the patch value so caller mutations of the
            # patch don't propagate into the result either.
            result[key] = copy.deepcopy(value)
    return result


def validate_settings_against_capabilities(
    settings: Mapping[str, Any],
    capabilities: Sequence[Capability],
) -> None:
    """Validate `settings` against the union of `capabilities`'
    settings_schemas. Raises InvalidAssetSettingsError on failure.

    Returns None on success. Empty `capabilities` (Asset has no
    Capabilities assigned): all settings are orphan. STRICT-mode
    rejection if `settings` is non-empty; empty `settings` passes
    trivially.
    """
    schemas = [c.settings_schema for c in capabilities if c.settings_schema is not None]
    schemaless_count = len(capabilities) - len(schemas)

    # Edge case: no assigned Capabilities and no settings -> trivially valid.
    if not capabilities and not settings:
        return

    # Edge case: no assigned Capabilities but non-empty settings -> orphan.
    # STRICT by default since there are no schemaless Capabilities to soften.
    if not capabilities and settings:
        keys = ", ".join(f"'{k}'" for k in sorted(settings.keys()))
        msg = f"key(s) {keys} cannot be set: Asset has no assigned Capabilities to validate against"
        raise InvalidAssetSettingsError(msg)

    # Detect true cross-Capability type conflicts BEFORE running
    # jsonschema-rs (the validator's error messages are less
    # operator-friendly than naming the conflicting Capabilities
    # ourselves).
    _check_cross_capability_type_conflicts(capabilities)

    # Build the mega-schema: allOf the per-Capability schemas. If
    # every assigned Capability has a schema, also add
    # `unevaluatedProperties: false` to reject orphan keys. If at
    # least one Capability is schemaless, skip the strict clause
    # (permissive mode tolerates unknown keys).
    mega: dict[str, Any] = {
        "$schema": DRAFT_2020_12_URI,
        "type": "object",
    }
    if schemas:
        mega["allOf"] = list(schemas)
    if schemaless_count == 0 and schemas:
        # Strict mode: enumerate every property name declared by any
        # schema, and reject anything else.
        declared_keys = _collect_declared_property_names(schemas)
        mega["properties"] = {k: True for k in declared_keys}
        mega["additionalProperties"] = False

    try:
        validator = jsonschema_rs.Draft202012Validator(mega)
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        msg = f"jsonschema-rs failed to compile the union schema: {exc}"
        raise InvalidAssetSettingsError(msg) from exc

    errors = list(validator.iter_errors(dict(settings)))
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.instance_path) or "<root>"
        msg = f"settings validation failed at {path}: {first.message}"
        raise InvalidAssetSettingsError(msg)


def _collect_declared_property_names(schemas: Sequence[dict[str, Any]]) -> set[str]:
    """Return the set of property names declared by any schema's top-
    level `properties` dict. Used to drive strict-mode orphan
    rejection."""
    declared: set[str] = set()
    for schema in schemas:
        properties = schema.get("properties")
        if isinstance(properties, dict):
            declared.update(properties.keys())
    return declared


def _check_cross_capability_type_conflicts(capabilities: Sequence[Capability]) -> None:
    """Surface incompatible-type declarations across Capabilities
    BEFORE handing off to jsonschema-rs.

    Walks the top-level `properties` dicts of each Capability with a
    schema, and for every property name appearing in more than one
    Capability, asserts the declared `type` is identical. If types
    differ, raises InvalidAssetSettingsError naming both Capabilities
    and the offending key.

    This is the only kind of conflict that no value can satisfy
    under `allOf` semantics (constraint differences like minimum +
    minimum just intersect to the most restrictive).
    """
    # property_name -> list of (capability_id, declared_type)
    type_by_key: dict[str, list[tuple[str, Any]]] = {}
    for cap in capabilities:
        schema = cap.settings_schema
        if schema is None:
            continue
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            continue
        for prop_name, prop_schema in properties.items():  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(prop_schema, dict):
                continue
            declared_type = prop_schema.get("type")
            if declared_type is None:
                continue
            type_by_key.setdefault(prop_name, []).append((str(cap.id), declared_type))

    for prop_name, entries in type_by_key.items():
        types = {t for _, t in entries}
        if len(types) > 1:
            descriptions = "; ".join(f"Capability {cid}: {t}" for cid, t in entries)
            msg = (
                f"key '{prop_name}' has incompatible types across "
                f"Capabilities ({descriptions}); no value can satisfy "
                f"the union"
            )
            raise InvalidAssetSettingsError(msg)


__all__ = [
    "merge_patch",
    "validate_settings_against_capabilities",
]
