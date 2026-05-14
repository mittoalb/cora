"""Validate Plan.parameter_defaults against the owning Method's
parameters_schema (Phase 6g-b).

The 6g-a Method-side checker validates the SHAPE of the schema
itself (constrained subset). This module validates VALUES against
that schema using `jsonschema-rs`'s Draft 2020-12 validator.

## Strict when Method declares no schema (audit-driven reversal)

Originally shipped permissive: when `parameters_schema is None` the
defaults dict was accepted verbatim. The post-6g audit found this
was the wrong call — silent typos pass through to bad data, the
posture is inconsistent with 5g-c's strict zero-Capabilities mode,
and CORA's "Method declares the contract" value proposition argues
for failing fast when no contract exists.

Modern community consensus (post-6g research, May 2026): Ajv (the
dominant JSON Schema validator in the JS ecosystem) ships strict-
by-default specifically to prevent silent typos; Argo Workflows /
Kubeflow / Tekton all require parameters to be DECLARED in the
workflow template before runtime values can be passed. CORA's
new posture aligns with both.

Posture (this module's contract):

  - `parameters_schema is None` AND `parameter_defaults` is non-empty
    → raise `InvalidPlanParameterDefaultsError` with a clear message
    telling the operator to either declare a schema (an empty `{}`
    is valid for parameter-less Methods) or omit the defaults
  - `parameters_schema is None` AND `parameter_defaults` is empty
    → accept (no contract, no values, no conflict)
  - `parameters_schema = {}` (operator's explicit "no parameters")
    AND `parameter_defaults` is empty → accept
  - `parameters_schema = {}` AND `parameter_defaults` is non-empty
    → reject via jsonschema-rs (no properties declared)
  - `parameters_schema` declares the contract → validate against it

Operators wanting "Method has truly no parameters" declare an empty
schema `{}` explicitly via `update_method_parameters_schema`. The
small one-time friction is the explicit operator decision that lets
strict mode work safely.

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

    Strict when `method_parameters_schema is None`: empty defaults
    pass trivially, but ANY non-empty defaults dict raises
    `InvalidPlanParameterDefaultsError` with a clear message
    instructing the operator to declare a schema (even an empty
    `{}`) or omit the defaults. See module docstring for the
    audit-driven rationale.

    Raises `InvalidPlanParameterDefaultsError(reason)` with a path-
    prefixed diagnostic on validation failure.
    """
    if method_parameters_schema is None:
        if not parameter_defaults:
            # Empty defaults + no schema: trivially valid.
            return
        # Strict: non-empty defaults without a schema → reject.
        keys = ", ".join(f"'{k}'" for k in sorted(parameter_defaults.keys()))
        msg = (
            f"Method declares no parameters_schema; cannot accept defaults "
            f"for key(s) {keys}. Either declare a parameters_schema (an empty "
            f"`{{}}` is valid for parameter-less Methods) or omit the defaults."
        )
        raise InvalidPlanParameterDefaultsError(msg)

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
