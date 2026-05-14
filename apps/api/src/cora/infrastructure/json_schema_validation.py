"""Shared JSON Schema validators for the schema-validated-values pattern.

CORA has two structurally identical validation surfaces across BCs:

  - **Schema declaration validators** check that a stored schema is
    well-formed and in CORA's constrained subset. Used at write time
    when an operator submits a new schema (Capability.settings_schema
    via 5g-a's `update_capability_schema`; Method.parameters_schema
    via 6g-a's `update_method_parameters_schema`).
  - **Values-against-schema validators** check that a values dict
    conforms to a previously-declared schema. Used when the values
    are written (Plan.parameter_defaults via 6g-b; Run.effective_parameters
    via 6g-c) or when an Asset's settings are updated against the
    union of assigned Capabilities' schemas (5g-c).

This module hoists the shared bits. Each BC keeps its own typed
error class (Capability/Method/Plan/Run/Asset specific) so HTTP
exception handlers stay aligned with their BC namespace; the error
class is passed in as a parameter. Mirrors the `json_schema_subset`
hoist precedent (each BC's wrapper ~10 lines instead of ~80).

## Pattern memo

The "schema-validated values" pattern has two halves:
  1. **Declarer aggregate** owns the optional schema (Capability,
     Method). Schema mutations validate well-formedness.
  2. **Carrier aggregate** owns the values (Asset, Plan, Run).
     Values mutations validate against the declarer's schema.

Both halves use the same constrained JSON Schema subset
(`cora.infrastructure.json_schema_subset`) and the same
`jsonschema-rs` Draft 2020-12 engine. The strict-by-default posture
(post-6g audit) is uniform across both halves: missing schema +
non-empty values → reject with operator-facing guidance.

See `[[project_schema_validated_values_pattern]]` for the full
family map (5g-a/c + 6g-a/b/c) and operator vocabulary mapping
(settings vs parameters preserved per industrial convention).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Mapping
from typing import Any

import jsonschema_rs

from cora.infrastructure.json_schema_subset import DRAFT_2020_12_URI, check_subset


def validate_schema_declaration(
    schema: dict[str, Any],
    *,
    error_class: type[ValueError],
) -> None:
    """Validate that `schema` is a well-formed JSON Schema in CORA's
    constrained subset (declarer-side write-time check).

    Three failure modes, all raised as `error_class(reason)`:
      1. Missing or wrong `$schema` declaration
      2. Forbidden keyword used (per `json_schema_subset.check_subset`)
      3. jsonschema-rs rejects the schema as malformed (e.g. an
         invalid `pattern` regex)

    Returns None on success. Caller persists the schema as-is; runtime
    validation of values against it (5g-c / 6g-b / 6g-c) reuses
    `validate_values_against_schema` below.

    Used by 5g-a (Capability.settings_schema) and 6g-a
    (Method.parameters_schema).
    """
    declared = schema.get("$schema")
    if declared != DRAFT_2020_12_URI:
        msg = (
            f"$schema must be exactly {DRAFT_2020_12_URI!r} "
            f"(got: {declared!r}); CORA locks Draft 2020-12"
        )
        raise error_class(msg)

    check_subset(schema, path="<root>", error_class=error_class)

    try:
        jsonschema_rs.Draft202012Validator(schema)
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        msg = f"jsonschema-rs rejected the schema as malformed: {exc}"
        raise error_class(msg) from exc


def validate_values_against_schema(
    values: Mapping[str, Any],
    schema: dict[str, Any] | None,
    *,
    error_class: type[ValueError],
    no_schema_message: str,
) -> None:
    """Validate a values dict against a JSON Schema (carrier-side
    write-time check). STRICT-by-default per the post-6g audit:
    schema=None + non-empty values rejects.

    The `no_schema_message` template MUST contain a `{keys}`
    placeholder; the function fills in a comma-separated list of
    the offending keys (sorted, single-quoted) before raising.
    Each carrier wrapper supplies its own operator-facing message
    (Plan / Run / Asset).

    Behavior:
      - schema is None AND values is empty → accept (trivially valid)
      - schema is None AND values is non-empty → raise error_class
        with no_schema_message.format(keys=...)
      - schema is non-None AND values is empty → accept (no
        required-field check at this layer; required applies at the
        per-aggregate consumer point — for example, effective_parameters
        at Run start, 6g-c)
      - schema is non-None AND values is non-empty → compile via
        jsonschema-rs Draft 2020-12, run iter_errors, raise on first
        violation with path-prefixed diagnostic

    Used by 6g-b (Plan.parameter_defaults) and 6g-c (Run.effective_parameters).
    The Asset.settings validator (5g-c) builds a UNION mega-schema
    from multiple Capabilities first, then could reuse the
    iter_errors path here (currently retains its own implementation
    because the multi-source pre-step is BC-specific).
    """
    if schema is None:
        if not values:
            return
        keys = ", ".join(f"'{k}'" for k in sorted(values.keys()))
        raise error_class(no_schema_message.format(keys=keys))

    if not values:
        return

    try:
        validator = jsonschema_rs.Draft202012Validator(schema)
    except (jsonschema_rs.ValidationError, ValueError) as exc:
        msg = f"jsonschema-rs failed to compile the schema: {exc}"
        raise error_class(msg) from exc

    errors = list(validator.iter_errors(dict(values)))
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.instance_path) or "<root>"
        msg = f"validation failed at {path}: {first.message}"
        raise error_class(msg)


__all__ = [
    "validate_schema_declaration",
    "validate_values_against_schema",
]
