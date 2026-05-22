"""Validate Capability.parameter_schema against CORA's constrained
JSON Schema subset.

Capability.parameter_schema declares the DECLARATIVE CONTRACT for
the parameters any implementer (Method via 6l, Procedure via 10d)
must validate as a SUBSET of. The Method.parameters_schema (6g) is
the BINDING shape; cross-BC validation at define_method ensures
the binding fits within the contract.

Reuses the shared declarer-validator at
`cora.infrastructure.json_schema_validation` (same pattern as
Family.settings_schema validation in 5g-a, renamed in 5i). The
constrained subset rules are identical: `$schema`, `type`,
`required`, `properties`, `enum`, `minimum`, `maximum`, `pattern`
allowed; `$ref`, `oneOf`, `anyOf`, `allOf`, `not`, conditionals
forbidden.
"""

from typing import Any

from cora.infrastructure.json_schema_validation import validate_schema_declaration


class InvalidCapabilityParameterSchemaError(ValueError):
    """The supplied Capability parameter_schema is not a valid JSON
    Schema in CORA's constrained subset.

    Mapped to HTTP 400 by the Recipe BC's exception handler.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Capability parameter_schema: {reason}")
        self.reason = reason


def validate_capability_parameter_schema(schema: dict[str, Any]) -> None:
    """Validate that `schema` is a well-formed in-subset JSON Schema.

    Raises `InvalidCapabilityParameterSchemaError(reason)` on failure.
    Delegates to the shared declarer-validator.
    """
    validate_schema_declaration(schema, error_class=InvalidCapabilityParameterSchemaError)


__all__ = [
    "InvalidCapabilityParameterSchemaError",
    "validate_capability_parameter_schema",
]
