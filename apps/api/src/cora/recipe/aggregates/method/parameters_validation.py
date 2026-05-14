"""Validate Method.parameters_schema against CORA's constrained
JSON Schema subset (Phase 6g-a).

Method.parameters_schema declares the shape of parameter dicts that
downstream Plans (6g-b) and Runs (6g-c) carry for this Method. This
module is the write-time guard that ensures every persisted schema
is a valid, in-subset JSON Schema; the runtime validation of Plan
defaults and Run effective_parameters against this schema (6g-b /
6g-c) compiles via `jsonschema_rs.Draft202012Validator(schema)`.

## Constrained subset (locked in [[project_capability_settings_schema]])

Same subset as Capability.settings_schema. The whitelist + recursive
checker live in `cora.infrastructure.json_schema_subset` (hoisted in
6g-a once the third use site landed). This module wraps the shared
checker with the Method-specific error class and the
parameters-flavored docstring.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any

import jsonschema_rs

from cora.infrastructure.json_schema_subset import DRAFT_2020_12_URI, check_subset


class InvalidMethodParametersSchemaError(ValueError):
    """The supplied Method parameters_schema is not a valid JSON
    Schema in CORA's constrained subset.

    Three failure modes:
      1. Schema is not well-formed JSON Schema (jsonschema-rs raises
         on `Validator(schema)` construction).
      2. Schema uses a forbidden keyword (`$ref`, `oneOf`, etc.).
      3. Schema is missing the required `$schema` declaration.

    Mapped to HTTP 400 by the recipe BC's exception handler.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Method parameters_schema: {reason}")
        self.reason = reason


def validate_parameters_schema(schema: dict[str, Any]) -> None:
    """Validate that `schema` is a well-formed JSON Schema in CORA's
    constrained subset.

    Raises `InvalidMethodParametersSchemaError` on any of: missing or
    wrong `$schema` declaration, forbidden top-level / properties-level
    keyword, or jsonschema-rs rejecting the schema as malformed.

    Returns None on success. The caller persists the schema as-is;
    runtime validation of Plan.parameter_defaults and Run effective
    parameters against this schema (Phase 6g-b / 6g-c) reuses the
    same compilation path.
    """
    declared = schema.get("$schema")
    if declared != DRAFT_2020_12_URI:
        msg = (
            f"$schema must be exactly {DRAFT_2020_12_URI!r} "
            f"(got: {declared!r}); Phase 6g-a locks Draft 2020-12"
        )
        raise InvalidMethodParametersSchemaError(msg)

    check_subset(schema, path="<root>", error_class=InvalidMethodParametersSchemaError)

    try:
        jsonschema_rs.Draft202012Validator(schema)
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        msg = f"jsonschema-rs rejected the schema as malformed: {exc}"
        raise InvalidMethodParametersSchemaError(msg) from exc


__all__ = [
    "InvalidMethodParametersSchemaError",
    "validate_parameters_schema",
]
