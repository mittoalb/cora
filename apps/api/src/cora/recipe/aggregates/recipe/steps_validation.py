"""Cross-aggregate validation: Recipe step BindingRefs vs Capability.parameters_schema.

A Recipe's `steps` may carry `BindingRef(name=...)` sentinels that
resolve against operator-supplied bindings at expansion time. At
define-recipe-time AND version-recipe-time AND
register-procedure-from-recipe-time, the slice handler verifies each
`BindingRef.name` reachable inside `steps` REFERS TO a parameter
declared in the referenced `Capability.parameters_schema.properties`.
Catching unknown binding names at every Recipe lifecycle write AND at
expansion gives deployment authors a fast, exhaustive failure mode
for typos, stale renames, and the Capability-re-version race.

Eager re-validation at expansion time closes the race where Capability
was versioned independently after the Recipe's last write; the slice
loads the CURRENT Capability state and runs this validator. When the
schema has drifted such that the Recipe's BindingRefs no longer
resolve, the slice raises a dedicated stale-Capability error class
(defined in the slice module, not here).

Validation rules:
  - Every `BindingRef.name` reachable in the steps must appear in
    `parameters_schema["properties"]` (when `parameters_schema` is
    non-None).
  - If `parameters_schema` is None, the steps MUST contain zero
    `BindingRef` instances (a Recipe with bindings against no schema
    is malformed).

Recursion: walks all `BindingRef`-eligible positions
(`RecipeSetpointStep.value`, `RecipeActionStep.params` per-key,
`RecipeCheckStep.criterion` thresholds at v1 do NOT carry BindingRef).
"""

from collections.abc import Mapping
from typing import Any, cast

from cora.recipe.aggregates.recipe.body import (
    BindingRef,
    RecipeActionStep,
    RecipeCheckStep,
    RecipeSetpointStep,
    RecipeStep,
)


class RecipeBindingReferencesUnknownParameterError(Exception):
    """A `BindingRef.name` in the Recipe's steps does not appear in `parameters_schema`.

    Carries the offending name + the set of declared parameter names
    so operators can spot a typo (or stale rename) immediately. Family:
    `Invalid<X>`. HTTP 422.
    """

    def __init__(self, name: str, schema_properties: frozenset[str]) -> None:
        declared = sorted(schema_properties)
        super().__init__(
            f"Recipe steps reference unknown parameter {name!r}; "
            f"Capability.parameters_schema declares {declared!r}"
        )
        self.name = name
        self.schema_properties = schema_properties


class RecipeRequiresCapabilityParametersSchemaError(Exception):
    """Recipe steps contain `BindingRef`s but the referenced Capability has no schema.

    A Recipe with bindings cannot validate against a None
    `parameters_schema`; the operator needs to either drop the
    bindings or first set a parameters_schema on the referenced
    Capability. Family: `Invalid<X>`. HTTP 422.
    """

    def __init__(self, binding_names: frozenset[str]) -> None:
        names = sorted(binding_names)
        super().__init__(
            f"Recipe has {len(names)} binding reference(s) {names!r} "
            f"but the referenced Capability.parameters_schema is None"
        )
        self.binding_names = binding_names


def _binding_names_in_value(value: Any) -> frozenset[str]:
    if isinstance(value, BindingRef):
        return frozenset({value.name})
    return frozenset()


def _binding_names_in_step(step: object) -> frozenset[str]:
    if isinstance(step, RecipeSetpointStep):
        return _binding_names_in_value(step.value)
    if isinstance(step, RecipeActionStep):
        names: set[str] = set()
        for val in step.params.values():
            names |= _binding_names_in_value(val)
        return frozenset(names)
    if isinstance(step, RecipeCheckStep):
        return frozenset()
    return frozenset()


def collect_binding_names(steps: tuple[RecipeStep, ...]) -> frozenset[str]:
    """Return the set of `BindingRef.name` values reachable inside the step sequence."""
    names: set[str] = set()
    for step in steps:
        names |= _binding_names_in_step(step)
    return frozenset(names)


def validate_recipe_steps_against_capability_schema(
    steps: tuple[RecipeStep, ...],
    parameters_schema: Mapping[str, Any] | None,
) -> None:
    """Verify every `BindingRef` in `steps` resolves to a declared parameter.

    Raises `RecipeRequiresCapabilityParametersSchemaError` if the steps
    have any `BindingRef` but `parameters_schema` is None. Raises
    `RecipeBindingReferencesUnknownParameterError` for the first
    BindingRef whose name is not in `parameters_schema["properties"]`.
    """
    binding_names = collect_binding_names(steps)
    if not binding_names:
        return
    if parameters_schema is None:
        raise RecipeRequiresCapabilityParametersSchemaError(binding_names)
    raw_properties = parameters_schema.get("properties", {})
    if isinstance(raw_properties, dict):
        typed_properties = cast("dict[str, Any]", raw_properties)
        declared: frozenset[str] = frozenset(typed_properties.keys())
    else:
        declared = frozenset()
    for name in sorted(binding_names):
        if name not in declared:
            raise RecipeBindingReferencesUnknownParameterError(name, declared)


__all__ = [
    "RecipeBindingReferencesUnknownParameterError",
    "RecipeRequiresCapabilityParametersSchemaError",
    "collect_binding_names",
    "validate_recipe_steps_against_capability_schema",
]
