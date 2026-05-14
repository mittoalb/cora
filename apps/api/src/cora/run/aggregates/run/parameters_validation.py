"""Validate Run effective_parameters against the owning Method's
parameters_schema (Phase 6g-c).

The 6g-a Method-side checker validates the SHAPE of the schema
itself. The 6g-b Plan-side validator validates DEFAULTS. This
module is the Run-side equivalent: validates the RESOLVED merge
(defaults + overrides) at start_run time. Delegates to the shared
values-validator at `cora.infrastructure.json_schema_validation`.
Strict-by-default when the schema is None (post-6g audit reversal;
mirrors 5g-c's "no Capabilities + non-empty settings → reject"
anchor).

## Module shape

Thin BC-specific adapter: defines `InvalidRunParametersError` on
`run.aggregates.run.state` (next to other Run domain errors) +
a one-liner `validate_effective_parameters_against_method_schema`
that delegates to the shared validator with the Run-specific
operator-facing error message. Mirrors the Plan-side adapter shape.
See [[project_run_parameters_design]] §audit-correction for the
strict posture rationale and
[[project_schema_validated_values_pattern]] for the cross-BC
implementation pattern.
"""

from collections.abc import Mapping
from typing import Any

from cora.infrastructure.json_schema_validation import validate_values_against_schema
from cora.run.aggregates.run.state import InvalidRunParametersError

_NO_SCHEMA_MESSAGE = (
    "Method declares no parameters_schema; cannot start Run with "
    "resolved parameters {keys}. Either declare a parameters_schema "
    "on the Method (an empty `{{}}` is valid for parameter-less "
    "Methods) or omit override_parameters AND clear Plan defaults."
)


def validate_effective_parameters_against_method_schema(
    effective_parameters: Mapping[str, Any],
    method_parameters_schema: dict[str, Any] | None,
) -> None:
    """Validate `effective_parameters` against the Method's schema.

    Strict when `method_parameters_schema is None`: empty effective
    parameters pass trivially, but ANY non-empty effective dict
    raises `InvalidRunParametersError` with operator guidance.
    Delegates to the shared values-validator.
    """
    validate_values_against_schema(
        effective_parameters,
        method_parameters_schema,
        error_class=InvalidRunParametersError,
        no_schema_message=_NO_SCHEMA_MESSAGE,
    )


__all__ = ["validate_effective_parameters_against_method_schema"]
