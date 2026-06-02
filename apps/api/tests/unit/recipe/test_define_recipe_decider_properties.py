"""Property-based tests for `define_recipe.decide` (Recipe BC).

Mirrors the `define_capability` decider-PBT pattern on a Recipe BC
create-style command. Universal claims across generated inputs:

  - state=None + valid command emits a single RecipeDefined with
    the injected new_id / now and preserves name / capability_id /
    steps verbatim.
  - state=Recipe always raises RecipeAlreadyExistsError, regardless
    of command.
  - Empty steps tuple always raises EmptyRecipeStepsError (via
    Recipe.__post_init__).
  - Pure: same (state, command, now, new_id) returns the same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.recipe.aggregates.recipe import (
    EmptyRecipeStepsError,
    Recipe,
    RecipeAlreadyExistsError,
    RecipeDefined,
    RecipeName,
    RecipeSetpointStep,
    RecipeStep,
)
from cora.recipe.features import define_recipe
from cora.recipe.features.define_recipe import DefineRecipe
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(min_size=1, max_size=200)
_STEP = st.builds(
    RecipeSetpointStep,
    address=st.text(min_size=1, max_size=20),
    value=st.floats(allow_nan=False, allow_infinity=False, width=32),
    verify=st.booleans(),
)
_STEPS = st.lists(_STEP, min_size=1, max_size=5).map(tuple)


def _command(
    *,
    name: str,
    capability_id: UUID,
    steps: tuple[RecipeStep, ...],
) -> DefineRecipe:
    return DefineRecipe(name=name, capability_id=capability_id, steps=steps)


def _recipe(recipe_id: UUID) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=RecipeName("R"),
        capability_id=recipe_id,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
    )


@pytest.mark.unit
@given(
    name=_NAME,
    capability_id=st.uuids(),
    steps=_STEPS,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_recipe_emits_exactly_one_event_with_injected_fields(
    name: str,
    capability_id: UUID,
    steps: tuple[RecipeStep, ...],
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream + valid command -> single RecipeDefined with injected ids/time."""
    command = _command(name=name, capability_id=capability_id, steps=steps)
    events = define_recipe.decide(state=None, command=command, now=now, new_id=new_id)
    assert events == [
        RecipeDefined(
            recipe_id=new_id,
            name=name.strip(),
            capability_id=capability_id,
            steps=steps,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    name=_NAME,
    capability_id=st.uuids(),
    steps=_STEPS,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_recipe_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    name: str,
    capability_id: UUID,
    steps: tuple[RecipeStep, ...],
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state -> RecipeAlreadyExistsError, regardless of command."""
    command = _command(name=name, capability_id=capability_id, steps=steps)
    with pytest.raises(RecipeAlreadyExistsError) as exc:
        define_recipe.decide(state=_recipe(existing_id), command=command, now=now, new_id=new_id)
    assert exc.value.recipe_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    capability_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_recipe_with_empty_steps_always_raises_empty(
    name: str,
    capability_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty steps tuple -> EmptyRecipeStepsError via Recipe.__post_init__."""
    command = _command(name=name, capability_id=capability_id, steps=())
    with pytest.raises(EmptyRecipeStepsError):
        define_recipe.decide(state=None, command=command, now=now, new_id=new_id)


@pytest.mark.unit
@given(
    name=_NAME,
    capability_id=st.uuids(),
    steps=_STEPS,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_recipe_is_pure_same_input_same_output(
    name: str,
    capability_id: UUID,
    steps: tuple[RecipeStep, ...],
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    command = _command(name=name, capability_id=capability_id, steps=steps)
    first = define_recipe.decide(state=None, command=command, now=now, new_id=new_id)
    second = define_recipe.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
