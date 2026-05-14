"""Validate Plan.parameter_defaults against the owning Method's
parameters_schema (Phase 6g-b).

The 6g-a Method-side checker validates the SHAPE of the schema
itself (constrained subset). This module validates VALUES against
that schema using `jsonschema-rs`'s Draft 2020-12 validator.

## Permissive when Method declares no schema

When `parameters_schema is None` the Method has no parameter
contract; this module returns silently regardless of what the
defaults dict contains. Locked posture per
[[project_run_parameters_design]] §6g-b. Asymmetric vs 5g-c's
Asset.settings (which is strict for zero-Capabilities) — Method-
without-schema is a legitimate workflow stage.

## Validation flow

For non-None schema:
  1. Compile the schema via `Draft202012Validator(schema)`. Failures
     here mean the Method's stored schema is malformed (shouldn't
     happen since 6g-a's `validate_parameters_schema` runs at write
     time, but we surface a clear error if it does).
  2. Run `iter_errors(defaults)` and surface the first violation
     with a path-prefixed diagnostic.

## Error shape

`InvalidPlanParameterDefaultsError` lives on `plan.state` next to
the other Plan domain errors. Mapped to HTTP 400 by the recipe BC's
exception handler.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Mapping
from typing import Any

import jsonschema_rs

from cora.recipe.aggregates.plan.state import InvalidPlanParameterDefaultsError


def validate_parameter_defaults_against_method_schema(
    parameter_defaults: Mapping[str, Any],
    method_parameters_schema: dict[str, Any] | None,
) -> None:
    """Validate `parameter_defaults` against the Method's schema.

    Permissive when `method_parameters_schema is None` — returns
    None without inspecting the defaults dict. Empty defaults are
    trivially valid in either mode.

    Raises `InvalidPlanParameterDefaultsError(reason)` with a path-
    prefixed diagnostic on validation failure.
    """
    if method_parameters_schema is None:
        return
    if not parameter_defaults:
        # Empty defaults satisfy any schema (no required-field check
        # at this layer; 'required' applies to the resolved
        # effective_parameters at Run start, 6g-c).
        return

    try:
        validator = jsonschema_rs.Draft202012Validator(method_parameters_schema)
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        msg = f"jsonschema-rs failed to compile the Method's parameters_schema: {exc}"
        raise InvalidPlanParameterDefaultsError(msg) from exc

    errors = list(validator.iter_errors(dict(parameter_defaults)))
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.instance_path) or "<root>"
        msg = f"validation failed at {path}: {first.message}"
        raise InvalidPlanParameterDefaultsError(msg)


__all__ = ["validate_parameter_defaults_against_method_schema"]
