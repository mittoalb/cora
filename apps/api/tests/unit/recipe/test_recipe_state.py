"""Unit tests for the Recipe aggregate's state, status, and value objects."""

from uuid import uuid4

import pytest

from cora.recipe.aggregates.recipe import (
    RECIPE_NAME_MAX_LENGTH,
    RECIPE_VERSION_TAG_MAX_LENGTH,
    EmptyRecipeStepsError,
    InvalidRecipeNameError,
    InvalidRecipeVersionTagError,
    Recipe,
    RecipeAlreadyExistsError,
    RecipeCannotDeprecateError,
    RecipeCannotVersionError,
    RecipeName,
    RecipeNotFoundError,
    RecipeSetpointStep,
    RecipeStatus,
)


def _steps() -> tuple[RecipeSetpointStep, ...]:
    return (RecipeSetpointStep(address="dev:x", value=1.0),)


@pytest.mark.unit
def test_recipe_status_values_match_bc_map() -> None:
    assert RecipeStatus.DEFINED.value == "Defined"
    assert RecipeStatus.VERSIONED.value == "Versioned"
    assert RecipeStatus.DEPRECATED.value == "Deprecated"


@pytest.mark.unit
def test_recipe_name_trims_whitespace() -> None:
    assert RecipeName("  tomography continuous  ").value == "tomography continuous"


@pytest.mark.unit
def test_recipe_name_rejects_empty_after_trim() -> None:
    with pytest.raises(InvalidRecipeNameError):
        RecipeName("   ")


@pytest.mark.unit
def test_recipe_name_rejects_too_long() -> None:
    too_long = "x" * (RECIPE_NAME_MAX_LENGTH + 1)
    with pytest.raises(InvalidRecipeNameError):
        RecipeName(too_long)


@pytest.mark.unit
def test_recipe_constructs_with_required_fields() -> None:
    rid = uuid4()
    cid = uuid4()
    recipe = Recipe(id=rid, name=RecipeName("R1"), capability_id=cid, steps=_steps())
    assert recipe.id == rid
    assert recipe.capability_id == cid
    assert recipe.status == RecipeStatus.DEFINED
    assert recipe.version is None
    assert recipe.replaced_by_recipe_id is None
    assert len(recipe.steps) == 1


@pytest.mark.unit
def test_recipe_rejects_empty_steps_at_post_init() -> None:
    with pytest.raises(EmptyRecipeStepsError):
        Recipe(id=uuid4(), name=RecipeName("R1"), capability_id=uuid4(), steps=())


@pytest.mark.unit
def test_recipe_already_exists_error_carries_recipe_id() -> None:
    rid = uuid4()
    err = RecipeAlreadyExistsError(rid)
    assert err.recipe_id == rid
    assert str(rid) in str(err)


@pytest.mark.unit
def test_recipe_not_found_error_carries_recipe_id() -> None:
    rid = uuid4()
    err = RecipeNotFoundError(rid)
    assert err.recipe_id == rid


@pytest.mark.unit
def test_recipe_cannot_version_error_carries_status() -> None:
    rid = uuid4()
    err = RecipeCannotVersionError(rid, RecipeStatus.DEPRECATED)
    assert err.recipe_id == rid
    assert err.current_status == RecipeStatus.DEPRECATED
    assert "Deprecated" in str(err)


@pytest.mark.unit
def test_recipe_cannot_deprecate_error_carries_status() -> None:
    rid = uuid4()
    err = RecipeCannotDeprecateError(rid, RecipeStatus.DEPRECATED)
    assert err.recipe_id == rid
    assert err.current_status == RecipeStatus.DEPRECATED


@pytest.mark.unit
def test_invalid_recipe_version_tag_error_carries_value() -> None:
    err = InvalidRecipeVersionTagError("")
    assert err.value == ""
    too_long = "v" * (RECIPE_VERSION_TAG_MAX_LENGTH + 1)
    err2 = InvalidRecipeVersionTagError(too_long)
    assert err2.value == too_long


@pytest.mark.unit
def test_empty_recipe_steps_error_message_is_actionable() -> None:
    err = EmptyRecipeStepsError()
    assert "non-empty" in str(err).lower()


@pytest.mark.unit
def test_recipe_is_frozen_dataclass() -> None:
    from dataclasses import FrozenInstanceError

    recipe = Recipe(id=uuid4(), name=RecipeName("R1"), capability_id=uuid4(), steps=_steps())
    with pytest.raises(FrozenInstanceError):
        recipe.version = "v1"  # type: ignore[misc]
