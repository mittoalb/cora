"""Validate Plan.parameter_defaults against the owning Method's
parameters_schema (Phase 6g-b).

The 6g-a Method-side checker validates the SHAPE of the schema
itself. This module validates VALUES against that schema by
delegating to the shared values-validator at
`cora.infrastructure.json_schema_validation`. Strict-by-default
when the schema is None (post-6g audit reversal; mirrors 5g-c's
"no Capabilities + non-empty settings → reject" anchor).

## Module shape

Thin BC-specific adapter: defines `InvalidPlanParameterDefaultsError`
on `plan.state` (next to other Plan domain errors) + a one-liner
`validate_parameter_defaults_against_method_schema` that delegates
to the shared validator with the Plan-specific operator-facing
error message. See [[project_run_parameters_design]] §audit-correction
for the strict posture rationale and
[[project_schema_validated_values_pattern]] for the cross-BC
implementation pattern.
"""

from collections.abc import Mapping
from typing import Any

from cora.infrastructure.json_schema_validation import validate_values_against_schema
from cora.recipe.aggregates.plan.state import InvalidPlanParameterDefaultsError

_NO_SCHEMA_MESSAGE = (
    "Method declares no parameters_schema; cannot accept defaults "
    "for key(s) {keys}. Either declare a parameters_schema (an empty "
    "`{{}}` is valid for parameter-less Methods) or omit the defaults."
)


def validate_parameter_defaults_against_method_schema(
    parameter_defaults: Mapping[str, Any],
    method_parameters_schema: dict[str, Any] | None,
) -> None:
    """Validate `parameter_defaults` against the Method's schema.

    Strict when `method_parameters_schema is None`: empty defaults
    pass trivially, but ANY non-empty defaults dict raises
    `InvalidPlanParameterDefaultsError` with operator guidance.
    Delegates to the shared values-validator.
    """
    validate_values_against_schema(
        parameter_defaults,
        method_parameters_schema,
        error_class=InvalidPlanParameterDefaultsError,
        no_schema_message=_NO_SCHEMA_MESSAGE,
    )


__all__ = ["validate_parameter_defaults_against_method_schema"]
