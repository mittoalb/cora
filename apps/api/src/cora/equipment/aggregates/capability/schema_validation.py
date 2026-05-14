"""Validate Capability.settings_schema against CORA's constrained
JSON Schema subset (Phase 5g-a).

Capability.settings_schema declares the shape of Asset.settings keys
this Capability "owns". When an Asset.settings update lands in
Phase 5g-c, the validator unions all assigned Capabilities' schemas
and rejects keys / values that don't conform. This module is the
write-time guard that ensures every persisted schema is a valid,
in-subset JSON Schema; the runtime Asset.settings validation hook
in 5g-c reuses the same compilation path.

## Constrained subset (locked in [[project_capability_settings_schema]])

The subset whitelist + recursive checker live in
`cora.infrastructure.json_schema_subset` (hoisted in 6g-a once the
third use site landed: this module + Asset settings union compile +
Method.parameters_schema). This module wraps the shared checker with
the Capability-specific error class and the Capability-flavored
docstring.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any

import jsonschema_rs

from cora.infrastructure.json_schema_subset import DRAFT_2020_12_URI, check_subset


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
    if declared != DRAFT_2020_12_URI:
        msg = (
            f"$schema must be exactly {DRAFT_2020_12_URI!r} "
            f"(got: {declared!r}); Phase 5g-a locks Draft 2020-12"
        )
        raise InvalidCapabilitySchemaError(msg)

    check_subset(schema, path="<root>", error_class=InvalidCapabilitySchemaError)

    try:
        jsonschema_rs.Draft202012Validator(schema)
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        msg = f"jsonschema-rs rejected the schema as malformed: {exc}"
        raise InvalidCapabilitySchemaError(msg) from exc


__all__ = [
    "InvalidCapabilitySchemaError",
    "validate_settings_schema",
]
