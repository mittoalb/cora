"""Unit tests for the `version_recipe` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.recipe import (
    EmptyRecipeStepsError,
    InvalidRecipeVersionTagError,
    Recipe,
    RecipeCannotVersionError,
    RecipeName,
    RecipeNotFoundError,
    RecipeSetpointStep,
    RecipeStatus,
    RecipeVersioned,
)
from cora.recipe.features.version_recipe import VersionRecipe, decide

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _state(status: RecipeStatus = RecipeStatus.DEFINED) -> Recipe:
    return Recipe(
        id=uuid4(),
        name=RecipeName("R"),
        capability_id=uuid4(),
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        status=status,
    )


def _cmd(recipe_id: UUID, **overrides: object) -> VersionRecipe:
    base: dict[str, object] = dict(
        recipe_id=recipe_id,
        version_tag="v1",
        steps=(RecipeSetpointStep(address="dev:x", value=2.0),),
    )
    base.update(overrides)
    return VersionRecipe(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_decide_emits_recipe_versioned_when_state_defined() -> None:
    state = _state(RecipeStatus.DEFINED)
    events = decide(state=state, command=_cmd(state.id), now=_NOW)
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, RecipeVersioned)
    assert event.recipe_id == state.id
    assert event.version_tag == "v1"


@pytest.mark.unit
def test_decide_emits_recipe_versioned_when_state_versioned() -> None:
    state = _state(RecipeStatus.VERSIONED)
    events = decide(state=state, command=_cmd(state.id, version_tag="v2"), now=_NOW)
    assert len(events) == 1
    assert events[0].version_tag == "v2"


@pytest.mark.unit
def test_decide_raises_not_found_when_state_none() -> None:
    rid = uuid4()
    with pytest.raises(RecipeNotFoundError) as exc:
        decide(state=None, command=_cmd(rid), now=_NOW)
    assert exc.value.recipe_id == rid


@pytest.mark.unit
def test_decide_raises_cannot_version_when_state_deprecated() -> None:
    state = _state(RecipeStatus.DEPRECATED)
    with pytest.raises(RecipeCannotVersionError) as exc:
        decide(state=state, command=_cmd(state.id), now=_NOW)
    assert exc.value.current_status == RecipeStatus.DEPRECATED


@pytest.mark.unit
def test_decide_raises_on_whitespace_only_version_tag() -> None:
    state = _state()
    with pytest.raises(InvalidRecipeVersionTagError):
        decide(state=state, command=_cmd(state.id, version_tag="   "), now=_NOW)


@pytest.mark.unit
def test_decide_trims_version_tag() -> None:
    state = _state()
    events = decide(state=state, command=_cmd(state.id, version_tag="  v3  "), now=_NOW)
    assert events[0].version_tag == "v3"


@pytest.mark.unit
def test_decide_raises_on_empty_steps() -> None:
    state = _state()
    with pytest.raises(EmptyRecipeStepsError):
        decide(state=state, command=_cmd(state.id, steps=()), now=_NOW)


@pytest.mark.unit
def test_decide_emits_event_on_byte_equal_re_call() -> None:
    """Re-attestation is the audit signal; no no-op rule. Mirrors version_capability."""
    state = _state(RecipeStatus.VERSIONED)
    steps = (RecipeSetpointStep(address="dev:x", value=9.0),)
    cmd = _cmd(state.id, version_tag="v9", steps=steps)
    first = decide(state=state, command=cmd, now=_NOW)
    second = decide(state=state, command=cmd, now=_NOW)
    assert first == second
    assert len(first) == 1
