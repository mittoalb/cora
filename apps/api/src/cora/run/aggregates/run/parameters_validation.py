"""Validate Run effective_parameters against the owning Method's
parameters_schema (Phase 6g-c).

The 6g-a Method-side checker validates the SHAPE of the schema
itself. The 6g-b Plan-side validator validates DEFAULTS against
that schema. This module is the Run-side equivalent: validates the
RESOLVED merge (defaults + overrides) at start_run time.

## Strict when Method declares no schema (audit-driven reversal)

Originally shipped permissive: when `parameters_schema is None`
the effective dict was accepted verbatim. The post-6g audit
flipped this to strict to align with 6g-b's Plan-side reversal.
See [[project_run_parameters_design]] §audit-correction for the
shared rationale: silent typos pass through to bad data, the
original posture was inconsistent with 5g-c's strict zero-
Capabilities mode, and CORA's "Method declares the contract" value
proposition argues for failing fast.

Modern community consensus (post-6g research, May 2026): Ajv
defaults to strict mode to prevent silent typos; Argo Workflows
requires parameters DECLARED in the template before runtime values
can be passed. CORA aligns with both.

Posture (this module's contract):

  - `parameters_schema is None` AND `effective_parameters` is
    non-empty → raise `InvalidRunParametersError` with a clear
    message; operator must declare a schema (an empty `{}` is
    valid for parameter-less Methods) or omit the overrides
  - `parameters_schema is None` AND `effective_parameters` is
    empty → accept (no contract, no values, no conflict)
  - `parameters_schema = {}` (operator's explicit "no parameters")
    AND `effective_parameters` is empty → accept
  - `parameters_schema = {}` AND non-empty effective → reject
    via jsonschema-rs (no properties declared)
  - `parameters_schema` declares the contract → validate

The strict posture means `start_run` against a no-schema Method
without overrides keeps working (operator just used the empty
default). It only fails when the operator (or Plan defaults)
actually try to push values without a contract.

## Error shape

`InvalidRunParametersError` lives on `run.aggregates.run.state`
next to the other Run domain errors. Mapped to HTTP 400 by the run
BC's exception handler.

## Why a Run-side module instead of reusing the Plan-side function

Symmetry: each BC owns its own typed error class so logs and
exception handlers stay aligned with their BC namespace (recipe vs
run). The validation logic is identical in shape but the error
class differs. If a third use site appears, hoist the shared bits
to `cora.infrastructure.json_schema_validation` (matching the 6g-a
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

    Strict when `method_parameters_schema is None`: empty effective
    parameters pass trivially, but ANY non-empty effective dict
    raises `InvalidRunParametersError` with a clear message
    instructing the operator to declare a schema (even an empty
    `{}`) or omit the overrides. See module docstring for the
    audit-driven rationale.

    Raises `InvalidRunParametersError(reason)` with a path-prefixed
    diagnostic on validation failure.
    """
    if method_parameters_schema is None:
        if not effective_parameters:
            # Empty effective + no schema: trivially valid.
            return
        # Strict: non-empty effective without a schema → reject.
        keys = ", ".join(f"'{k}'" for k in sorted(effective_parameters.keys()))
        msg = (
            f"Method declares no parameters_schema; cannot start Run with "
            f"resolved parameters {keys}. Either declare a parameters_schema "
            f"on the Method (an empty `{{}}` is valid for parameter-less "
            f"Methods) or omit parameter_overrides AND clear Plan defaults."
        )
        raise InvalidRunParametersError(msg)

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
