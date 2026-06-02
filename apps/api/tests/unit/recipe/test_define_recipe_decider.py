"""Unit tests for the `define_recipe` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.recipe import (
    BindingRef,
    EmptyRecipeStepsError,
    InvalidRecipeNameError,
    Recipe,
    RecipeAlreadyExistsError,
    RecipeDefined,
    RecipeName,
    RecipeSetpointStep,
)
from cora.recipe.features.define_recipe import DefineRecipe, decide

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _cmd(**overrides: object) -> DefineRecipe:
    base: dict[str, object] = dict(
        name="R1",
        capability_id=uuid4(),
        steps=(RecipeSetpointStep(address="dev:x", value=BindingRef("angle")),),
    )
    base.update(overrides)
    return DefineRecipe(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_decide_emits_recipe_defined_for_fresh_stream() -> None:
    new_id = uuid4()
    events = decide(state=None, command=_cmd(name="tomography"), now=_NOW, new_id=new_id)
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, RecipeDefined)
    assert event.recipe_id == new_id
    assert event.name == "tomography"


@pytest.mark.unit
def test_decide_raises_already_exists_when_state_present() -> None:
    state = Recipe(
        id=uuid4(),
        name=RecipeName("R"),
        capability_id=uuid4(),
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
    )
    with pytest.raises(RecipeAlreadyExistsError) as exc:
        decide(state=state, command=_cmd(), now=_NOW, new_id=uuid4())
    assert exc.value.recipe_id == state.id


@pytest.mark.unit
def test_decide_raises_on_whitespace_only_name() -> None:
    with pytest.raises(InvalidRecipeNameError):
        decide(state=None, command=_cmd(name="   "), now=_NOW, new_id=uuid4())


@pytest.mark.unit
def test_decide_raises_on_empty_steps() -> None:
    with pytest.raises(EmptyRecipeStepsError):
        decide(state=None, command=_cmd(steps=()), now=_NOW, new_id=uuid4())


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    events = decide(state=None, command=_cmd(name="  R  "), now=_NOW, new_id=uuid4())
    assert events[0].name == "R"


@pytest.mark.unit
def test_decide_preserves_steps_verbatim() -> None:
    steps = (
        RecipeSetpointStep(address="dev:rot", value=BindingRef("angle")),
        RecipeSetpointStep(address="dev:z", value=1.5),
    )
    events = decide(state=None, command=_cmd(steps=steps), now=_NOW, new_id=uuid4())
    assert events[0].steps == steps


@pytest.mark.unit
def test_decide_is_pure() -> None:
    new_id = uuid4()
    cap_id = uuid4()
    e1 = decide(state=None, command=_cmd(capability_id=cap_id), now=_NOW, new_id=new_id)
    e2 = decide(state=None, command=_cmd(capability_id=cap_id), now=_NOW, new_id=new_id)
    assert e1 == e2
