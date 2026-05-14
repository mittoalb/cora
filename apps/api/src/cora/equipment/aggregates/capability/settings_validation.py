"""Validate Capability.settings_schema against CORA's constrained
JSON Schema subset (Phase 5g-a).

Capability.settings_schema declares the shape of Asset.settings keys
this Capability "owns". This module is the write-time guard via the
shared declarer-validator at
`cora.infrastructure.json_schema_validation`. The runtime values
validation (5g-c) lives in `asset/settings_validation.py` and uses
the union mega-schema path.

## Constrained subset

See `cora.infrastructure.json_schema_subset` for the allowed
keyword whitelist (`$schema`, `type`, `required`, `properties`,
`enum`, `minimum`, `maximum`, `pattern`). Forbidden everywhere:
`$ref`, `oneOf`, `anyOf`, `allOf`, `not`, conditionals.

## Module shape

This module is a thin BC-specific adapter: it defines the
`InvalidCapabilitySettingsSchemaError` exception class and a one-liner
`validate_settings_schema` that delegates to the shared validator.
Mirrors the `validate_name` hoist precedent (each VO type keeps
its own error class, shared trim logic in
`cora.infrastructure.name`).
"""

from typing import Any

from cora.infrastructure.json_schema_validation import validate_schema_declaration


class InvalidCapabilitySettingsSchemaError(ValueError):
    """The supplied Capability settings_schema is not a valid JSON
    Schema in CORA's constrained subset.

    Three failure modes (handled by the shared validator):
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
    """Validate that `schema` is a well-formed in-subset JSON Schema.

    Raises `InvalidCapabilitySettingsSchemaError(reason)` on missing/wrong
    `$schema`, forbidden keyword, or jsonschema-rs malformedness.
    Delegates to the shared declarer-validator.
    """
    validate_schema_declaration(schema, error_class=InvalidCapabilitySettingsSchemaError)


__all__ = [
    "InvalidCapabilitySettingsSchemaError",
    "validate_settings_schema",
]
