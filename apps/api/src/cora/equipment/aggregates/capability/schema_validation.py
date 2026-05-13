"""Validate Capability.settings_schema against CORA's constrained
JSON Schema subset (Phase 5g-a).

Capability.settings_schema declares the shape of Asset.settings keys
this Capability "owns". When an Asset.settings update lands in
Phase 5g-c, the validator unions all assigned Capabilities' schemas
and rejects keys / values that don't conform. This module is the
write-time guard that ensures every persisted schema is a valid,
in-subset JSON Schema; the runtime Asset.settings validation hook
in 5g-c reuses the same compilation path.

## Constrained subset (locked in project_capability_settings_schema)

Every Capability schema MUST include `"$schema":
"https://json-schema.org/draft/2020-12/schema"`. Top-level keys are
restricted to: `$schema`, `type`, `required`, `properties`, `enum`,
`minimum`, `maximum`, `pattern`. Properties values follow the same
restriction recursively. Forbidden: `$ref`, `oneOf`, `anyOf`,
`allOf`, `not`, conditionals, `additionalProperties` /
`unevaluatedProperties` / `prefixItems` / `$dynamicRef`.

Rationale: smaller validation surface, clearer error messages,
predictable validator behavior across `jsonschema-rs` versions.
Future expansion via additive widening of `_ALLOWED_SCHEMA_KEYS`
when a real use case demands it.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any

import jsonschema_rs

_DRAFT_2020_12_URI = "https://json-schema.org/draft/2020-12/schema"

# Top-level + properties-level keys allowed in CORA's subset.
# Every other JSON Schema keyword (including $ref / oneOf / anyOf /
# allOf / conditionals / additionalProperties / etc.) is rejected.
_ALLOWED_SCHEMA_KEYS: frozenset[str] = frozenset(
    {
        "$schema",
        "type",
        "required",
        "properties",
        "enum",
        "minimum",
        "maximum",
        "pattern",
    }
)


class InvalidCapabilitySchemaError(ValueError):
    """The supplied Capability settings_schema is not a valid JSON
    Schema in CORA's constrained subset.

    Three failure modes:
      1. Schema is not well-formed JSON Schema (jsonschema-rs raises
         on `Validator(schema)` construction).
      2. Schema uses a forbidden keyword (`$ref`, `oneOf`, etc.).
      3. Schema is missing the required `$schema` declaration.

    Mapped to HTTP 400 by the equipment BC's exception handler.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Capability settings_schema: {reason}")
        self.reason = reason


def validate_settings_schema(schema: dict[str, Any]) -> None:
    """Validate that `schema` is a well-formed JSON Schema in CORA's
    constrained subset.

    Raises `InvalidCapabilitySchemaError` on any of: missing or wrong
    `$schema` declaration, forbidden top-level / properties-level
    keyword, or jsonschema-rs rejecting the schema as malformed.

    Returns None on success. The caller persists the schema as-is;
    runtime validation of Asset.settings against this schema (Phase
    5g-c) compiles via `jsonschema_rs.Draft202012Validator(schema)`
    and uses the resulting validator to check incoming dicts.
    """
    declared = schema.get("$schema")
    if declared != _DRAFT_2020_12_URI:
        msg = (
            f"$schema must be exactly {_DRAFT_2020_12_URI!r} "
            f"(got: {declared!r}); Phase 5g-a locks Draft 2020-12"
        )
        raise InvalidCapabilitySchemaError(msg)

    _check_subset(schema, path="<root>")

    try:
        jsonschema_rs.Draft202012Validator(schema)
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        msg = f"jsonschema-rs rejected the schema as malformed: {exc}"
        raise InvalidCapabilitySchemaError(msg) from exc


def _check_subset(node: dict[str, Any], *, path: str) -> None:
    """Recursively assert that `node` only uses keys in the allowed
    subset. Recurses into `properties.<name>` (each value is itself
    a schema)."""
    forbidden = set(node.keys()) - _ALLOWED_SCHEMA_KEYS
    if forbidden:
        msg = (
            f"forbidden keyword(s) {sorted(forbidden)} at {path}; "
            f"CORA's subset allows only {sorted(_ALLOWED_SCHEMA_KEYS)}"
        )
        raise InvalidCapabilitySchemaError(msg)

    properties = node.get("properties")
    if properties is None:
        return
    if not isinstance(properties, dict):
        msg = f"properties at {path} must be a dict (got: {type(properties).__name__})"
        raise InvalidCapabilitySchemaError(msg)

    for prop_name, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            msg = (
                f"properties.{prop_name} at {path} must be a schema dict "
                f"(got: {type(prop_schema).__name__})"
            )
            raise InvalidCapabilitySchemaError(msg)
        # Properties-level schemas don't need their own $schema
        # declaration; only the root carries it. So we exclude
        # $schema from the allowed set for nested checks. Doing that
        # by passing a different allowed set would clutter the API;
        # instead, allow $schema everywhere (harmless at nested
        # levels) and document.
        _check_subset(prop_schema, path=f"{path}.properties.{prop_name}")


__all__ = [
    "InvalidCapabilitySchemaError",
    "validate_settings_schema",
]
