"""Catalog of well-known `rule` string constants.

The Decision BC's `rule` field is intentionally open
free-form (per gate-review Q5: new rules arrive without schema
migration). This module documents the canonical strings for
facilities aligning with established standards. Operators reference
rules by symbol (`ISO17025_SIMPLE_ACCEPTANCE`) instead of literal
string for grep-friendliness, IDE autocomplete, and refactor
safety. The BC does NOT validate against this catalog: any
free-form string remains valid (forward-compat by design).

## Naming convention

Well-known rule strings follow `<framework>:<section>:<variant>`:

  - `iso17025:7.1.3:simple_acceptance`, ISO 17025 Clause 7.1.3
    simple-acceptance decision rule (no guardband; conformity
    when measurement falls within tolerance)
  - `iso17025:7.1.3:guardband`, same clause, with measurement-
    uncertainty-derived guardband applied
  - `iso17025:7.1.3:non_binary`, ternary or N-ary rule
    (Conformity / Non-Conformity / Indeterminate)
  - `cora:policy:<context>:<version>`, CORA-internal policy
    rules (versioned because they evolve)
  - `<facility>:<system>:<rule_id>`, facility-specific rules
    (for example `aps:bls:32id_safety_v2`)

The catalog is INTENTIONALLY a starter set, not exhaustive.
Facilities adding their own well-known rules should extend their
own facility-specific catalog module rather than modifying CORA's.

## Why a separate module (not state.py)

`rule` is an open vocabulary that operators extend.
DECISION_CONTEXT_* constants live in state.py because contexts
are a closed set the BC ships. Rules are discoverable surface
deserved their own namespace, paralleling OpenTelemetry's
`opentelemetry.semconv.attributes` pattern.
"""

# ISO 17025 Clause 7.1.3 family, the dominant lab-accreditation
# decision-rule citations.
ISO17025_SIMPLE_ACCEPTANCE = "iso17025:7.1.3:simple_acceptance"
"""Simple acceptance: conformity when the measured value falls
within the specification tolerance, no guardband applied. Lowest
audit weight when measurement uncertainty is non-trivial."""

ISO17025_GUARDBAND = "iso17025:7.1.3:guardband"
"""Guardband: tolerance is reduced by a function of the measurement
uncertainty before applying the conformity check. Used when the
risk of false acceptance must be controlled (per ILAC-G8:09/2019)."""

ISO17025_NON_BINARY = "iso17025:7.1.3:non_binary"
"""Non-binary decision rule: conformity outcome is ternary or
N-ary (typically Conformity / Non-Conformity / Indeterminate),
allowing for explicit indeterminate-zone handling."""

# CORA-internal policy rules (versioned).
CORA_RECIPE_APPROVAL_V1 = "cora:policy:recipe_approval:v1"
"""CORA-internal policy for Recipe approval decisions (Method /
Practice / Plan version review)."""

CORA_RUN_ABORT_V1 = "cora:policy:run_abort:v1"
"""CORA-internal policy governing operator-initiated Run aborts."""

CORA_RUN_STOP_V1 = "cora:policy:run_stop:v1"
"""CORA-internal policy governing operator-initiated controlled Run stops."""

CORA_RUN_TRUNCATE_V1 = "cora:policy:run_truncate:v1"
"""CORA-internal policy governing retroactive Run truncation
(known-dead Runs being closed)."""

CORA_DATASET_DISCARD_V1 = "cora:policy:dataset_discard:v1"
"""CORA-internal policy governing GDPR-shaped Dataset discard
operations."""


__all__ = [
    "CORA_DATASET_DISCARD_V1",
    "CORA_RECIPE_APPROVAL_V1",
    "CORA_RUN_ABORT_V1",
    "CORA_RUN_STOP_V1",
    "CORA_RUN_TRUNCATE_V1",
    "ISO17025_GUARDBAND",
    "ISO17025_NON_BINARY",
    "ISO17025_SIMPLE_ACCEPTANCE",
]
