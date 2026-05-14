"""Shared constrained JSON Schema subset checker.

CORA accepts a deliberately small subset of JSON Schema Draft 2020-12
for Capability.settings_schema (Phase 5g-a) and Method.parameters_schema
(Phase 6g-a). Both surfaces want the same forbidden-keyword posture
(no $ref, oneOf, allOf, conditionals, etc.), so the keyword whitelist
and recursive subset checker live here once and are wrapped per BC
with the appropriate domain error class.

Hoisted in 6g-a once the third use site landed (Capability schema +
Asset settings union compilation + Method parameters schema). Mirrors
the `validate_name` hoist precedent at 6e-1.

## Constrained subset (locked in [[project_capability_settings_schema]])

Top-level + properties-level keys allowed: `$schema`, `type`,
`required`, `properties`, `enum`, `minimum`, `maximum`, `pattern`.
Forbidden everywhere: `$ref`, `oneOf`, `anyOf`, `allOf`, `not`,
conditionals (`if`/`then`/`else`/`dependentSchemas`),
`additionalProperties` / `unevaluatedProperties` / `prefixItems` /
`$dynamicRef`, anything else.

When widening this set with a new RECURSIVE keyword (for example
`items` for arrays, `patternProperties` for prefix-keyed maps), you
MUST also extend `check_subset` to recurse into that keyword's
value(s). Forgetting to do so opens a hole: forbidden keywords
nested inside the new keyword would slip through.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any

DRAFT_2020_12_URI = "https://json-schema.org/draft/2020-12/schema"

ALLOWED_SCHEMA_KEYS: frozenset[str] = frozenset(
    {
        "$schema",
        "type",
        "required",
        "properties",
        "enum",
        "minimum",
        "maximum",
        "pattern",
    }
)


def check_subset(
    node: dict[str, Any],
    *,
    path: str,
    error_class: type[ValueError],
) -> None:
    """Recursively assert that `node` only uses keys in the allowed subset.

    Raises `error_class(reason)` on the first violation, where `reason`
    is a descriptive string. Recurses into `properties.<name>` (each
    value is itself a schema). The caller's `error_class` is what gets
    surfaced to the HTTP layer, so each BC keeps its own typed error
    while sharing the structural check.
    """
    forbidden = set(node.keys()) - ALLOWED_SCHEMA_KEYS
    if forbidden:
        msg = (
            f"forbidden keyword(s) {sorted(forbidden)} at {path}; "
            f"CORA's subset allows only {sorted(ALLOWED_SCHEMA_KEYS)}"
        )
        raise error_class(msg)

    properties = node.get("properties")
    if properties is None:
        return
    if not isinstance(properties, dict):
        msg = f"properties at {path} must be a dict (got: {type(properties).__name__})"
        raise error_class(msg)

    for prop_name, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            msg = (
                f"properties.{prop_name} at {path} must be a schema dict "
                f"(got: {type(prop_schema).__name__})"
            )
            raise error_class(msg)
        # Properties-level schemas don't need their own $schema
        # declaration; only the root carries it. We allow $schema
        # everywhere (harmless at nested levels) to keep the recursion
        # API simple. Pinned at both 5g-a and 6g-a test suites.
        check_subset(prop_schema, path=f"{path}.properties.{prop_name}", error_class=error_class)


__all__ = [
    "ALLOWED_SCHEMA_KEYS",
    "DRAFT_2020_12_URI",
    "check_subset",
]
