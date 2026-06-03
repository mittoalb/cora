"""Unit tests for `cora.recipe.aggregates.recipe.steps_validation`."""

from typing import Any

import pytest

from cora.recipe.aggregates.recipe import (
    BindingRef,
    RecipeActionStep,
    RecipeBindingReferencesUnknownParameterError,
    RecipeCheckStep,
    RecipeRequiresCapabilityParametersSchemaError,
    RecipeSetpointStep,
    collect_binding_names,
    validate_recipe_steps_against_capability_schema,
)


@pytest.mark.unit
def test_collect_binding_names_returns_empty_for_literal_only_steps() -> None:
    steps = (
        RecipeSetpointStep(address="dev:x", value=1.0),
        RecipeActionStep(name="wait", params={"seconds": 2.0}),
        RecipeCheckStep(address="dev:x", criterion={"kind": "equals", "expected": 1.0}),
    )
    assert collect_binding_names(steps) == frozenset()


@pytest.mark.unit
def test_collect_binding_names_picks_up_setpoint_binding() -> None:
    steps = (RecipeSetpointStep(address="dev:x", value=BindingRef("angle")),)
    assert collect_binding_names(steps) == frozenset({"angle"})


@pytest.mark.unit
def test_collect_binding_names_picks_up_action_param_bindings() -> None:
    steps = (
        RecipeActionStep(
            name="acquire",
            params={"dwell": BindingRef("dwell"), "label": "main"},
        ),
    )
    assert collect_binding_names(steps) == frozenset({"dwell"})


@pytest.mark.unit
def test_collect_binding_names_unions_across_steps() -> None:
    steps = (
        RecipeSetpointStep(address="dev:x", value=BindingRef("a")),
        RecipeActionStep(name="acquire", params={"b": BindingRef("b")}),
    )
    assert collect_binding_names(steps) == frozenset({"a", "b"})


@pytest.mark.unit
def test_validator_accepts_steps_with_no_bindings_when_schema_none() -> None:
    steps = (RecipeSetpointStep(address="dev:x", value=1.0),)
    validate_recipe_steps_against_capability_schema(steps, None)


@pytest.mark.unit
def test_validator_accepts_steps_with_bindings_when_schema_declares_them() -> None:
    steps = (RecipeSetpointStep(address="dev:x", value=BindingRef("angle")),)
    schema = {"type": "object", "properties": {"angle": {"type": "number"}}}
    validate_recipe_steps_against_capability_schema(steps, schema)


@pytest.mark.unit
def test_validator_rejects_bindings_when_schema_is_none() -> None:
    steps = (RecipeSetpointStep(address="dev:x", value=BindingRef("angle")),)
    with pytest.raises(RecipeRequiresCapabilityParametersSchemaError) as exc:
        validate_recipe_steps_against_capability_schema(steps, None)
    assert "angle" in str(exc.value)


@pytest.mark.unit
def test_validator_rejects_unknown_binding_against_schema() -> None:
    steps = (RecipeSetpointStep(address="dev:x", value=BindingRef("enrgy")),)
    schema = {"type": "object", "properties": {"energy": {"type": "number"}}}
    with pytest.raises(RecipeBindingReferencesUnknownParameterError) as exc:
        validate_recipe_steps_against_capability_schema(steps, schema)
    assert exc.value.name == "enrgy"
    assert exc.value.schema_properties == frozenset({"energy"})


@pytest.mark.unit
def test_validator_treats_non_dict_properties_as_empty() -> None:
    steps = (RecipeSetpointStep(address="dev:x", value=BindingRef("a")),)
    schema: dict[str, Any] = {"type": "object", "properties": []}
    with pytest.raises(RecipeBindingReferencesUnknownParameterError):
        validate_recipe_steps_against_capability_schema(steps, schema)


@pytest.mark.unit
def test_validator_error_message_lists_declared_names_sorted() -> None:
    steps = (RecipeSetpointStep(address="dev:x", value=BindingRef("zzz")),)
    schema: dict[str, Any] = {"type": "object", "properties": {"b": {}, "a": {}}}
    with pytest.raises(RecipeBindingReferencesUnknownParameterError) as exc:
        validate_recipe_steps_against_capability_schema(steps, schema)
    assert "['a', 'b']" in str(exc.value)
