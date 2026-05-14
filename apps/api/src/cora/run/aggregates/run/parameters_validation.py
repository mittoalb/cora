"""Validate Run effective_parameters against the owning Method's
parameters_schema (Phase 6g-c).

The 6g-a Method-side checker validates the SHAPE of the schema
itself. The 6g-b Plan-side validator validates DEFAULTS against
that schema. This module is the Run-side equivalent: validates the
RESOLVED merge (defaults + overrides) at start_run time.

## Permissive when Method declares no schema

When `parameters_schema is None` the Method has no parameter
contract; this module returns silently regardless of what the
effective dict contains. Same locked posture as 6g-b's
`validate_parameter_defaults_against_method_schema` (asymmetric vs
5g-c; see [[project_run_parameters_design]] §6g-b for the rationale).

## Validation flow

For non-None schema:
  1. Compile the schema via `Draft202012Validator(schema)`. Failures
     here mean the Method's stored schema is malformed (shouldn't
     happen since 6g-a's `validate_parameters_schema` runs at write
     time, but we surface a clear error if it does).
  2. Run `iter_errors(effective_parameters)` and surface the first
     violation with a path-prefixed diagnostic.

## Error shape

`InvalidRunParametersError` lives on `run.aggregates.run.state` next
to the other Run domain errors. Mapped to HTTP 400 by the run BC's
exception handler.

## Why a Run-side module instead of reusing the Plan-side function

Symmetry: each BC owns its own typed error class so logs and
exception handlers stay aligned with their BC namespace (recipe vs
run). The validation logic is identical in shape but the error class
differs. If a third use site appears, hoist the shared bits to
`cora.infrastructure.json_schema_validation` (matching the 6g-a
subset-checker hoist precedent).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Mapping
from typing import Any

import jsonschema_rs

from cora.run.aggregates.run.state import InvalidRunParametersError


def validate_effective_parameters_against_method_schema(
    effective_parameters: Mapping[str, Any],
    method_parameters_schema: dict[str, Any] | None,
) -> None:
    """Validate `effective_parameters` against the Method's schema.

    Permissive when `method_parameters_schema is None` — returns
    None without inspecting the dict. Empty effective_parameters
    are trivially valid in either mode (required-field check at
    this layer has the same forward-looking stance as 6g-b's Plan
    defaults: the resolved set is what governs the Run; if the
    Method's required keys aren't covered, jsonschema-rs surfaces
    that as a violation).

    Raises `InvalidRunParametersError(reason)` with a path-prefixed
    diagnostic on validation failure.
    """
    if method_parameters_schema is None:
        return
    if not effective_parameters:
        return

    try:
        validator = jsonschema_rs.Draft202012Validator(method_parameters_schema)
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        msg = f"jsonschema-rs failed to compile the Method's parameters_schema: {exc}"
        raise InvalidRunParametersError(msg) from exc

    errors = list(validator.iter_errors(dict(effective_parameters)))
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.instance_path) or "<root>"
        msg = f"validation failed at {path}: {first.message}"
        raise InvalidRunParametersError(msg)


__all__ = ["validate_effective_parameters_against_method_schema"]
