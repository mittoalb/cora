"""Property-based tests for the Recipe BindingRef-integrity validator.

Pins three invariants over Hypothesis-generated schema/steps pairs:
  - Steps with BindingRefs that fully cover a schema's declared
    properties pass validation
  - Steps with at least one BindingRef name absent from the schema
    raise `RecipeBindingReferencesUnknownParameterError`
  - Steps with BindingRefs against a None schema raise
    `RecipeRequiresCapabilityParametersSchemaError`
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cora.recipe.aggregates.recipe import (
    BindingRef,
    RecipeActionStep,
    RecipeBindingReferencesUnknownParameterError,
    RecipeRequiresCapabilityParametersSchemaError,
    RecipeSetpointStep,
    collect_binding_names,
    validate_recipe_steps_against_capability_schema,
)

_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        min_codepoint=48,
        max_codepoint=122,
    ),
    min_size=1,
    max_size=10,
)


@pytest.mark.unit
@settings(max_examples=50, deadline=2000)
@given(declared=st.sets(_name_strategy, min_size=1, max_size=5))
def test_validator_accepts_when_all_bindings_in_schema(declared: set[str]) -> None:
    schema = {"type": "object", "properties": {n: {"type": "number"} for n in declared}}
    steps = tuple(RecipeSetpointStep(address=f"dev:{n}", value=BindingRef(n)) for n in declared)
    validate_recipe_steps_against_capability_schema(steps, schema)


@pytest.mark.unit
@settings(max_examples=50, deadline=2000)
@given(
    declared=st.sets(_name_strategy, min_size=1, max_size=5),
    extra=_name_strategy,
)
def test_validator_rejects_when_any_binding_missing_from_schema(
    declared: set[str], extra: str
) -> None:
    if extra in declared:
        return  # vacuous; the bound name IS in the schema
    schema = {"type": "object", "properties": {n: {"type": "number"} for n in declared}}
    steps = (RecipeSetpointStep(address="dev:x", value=BindingRef(extra)),)
    with pytest.raises(RecipeBindingReferencesUnknownParameterError):
        validate_recipe_steps_against_capability_schema(steps, schema)


@pytest.mark.unit
@settings(max_examples=50, deadline=2000)
@given(names=st.sets(_name_strategy, min_size=1, max_size=5))
def test_validator_rejects_any_bindings_when_schema_is_none(names: set[str]) -> None:
    steps = tuple(RecipeSetpointStep(address=f"dev:{n}", value=BindingRef(n)) for n in names)
    with pytest.raises(RecipeRequiresCapabilityParametersSchemaError):
        validate_recipe_steps_against_capability_schema(steps, None)


@pytest.mark.unit
@settings(max_examples=50, deadline=2000)
@given(
    setpoint_bindings=st.sets(_name_strategy, max_size=3),
    action_bindings=st.sets(_name_strategy, max_size=3),
)
def test_collect_binding_names_equals_union_across_step_kinds(
    setpoint_bindings: set[str], action_bindings: set[str]
) -> None:
    steps: list[object] = []
    steps.extend(
        RecipeSetpointStep(address=f"dev:{n}", value=BindingRef(n)) for n in setpoint_bindings
    )
    if action_bindings:
        steps.append(
            RecipeActionStep(
                name="act",
                params={n: BindingRef(n) for n in action_bindings},
            )
        )
    expected = setpoint_bindings | action_bindings
    collected = collect_binding_names(tuple(steps))  # type: ignore[arg-type]
    assert collected == frozenset(expected)
