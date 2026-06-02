"""Unit tests for the `get_recipe` query handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.recipe import UnauthorizedError
from cora.recipe.aggregates.recipe import (
    RecipeDefined,
    RecipeSetpointStep,
    RecipeStatus,
    event_type_name,
    to_payload,
)
from cora.recipe.features import get_recipe
from cora.recipe.features.get_recipe import GetRecipe
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_RECIPE_ID = UUID("01900000-0000-7000-8000-00000000ab40")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ab41")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000c0f0")


async def _seed_recipe(store: InMemoryEventStore) -> None:
    event = RecipeDefined(
        recipe_id=_RECIPE_ID,
        name="R",
        capability_id=_CAPABILITY_ID,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Recipe",
        stream_id=_RECIPE_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=UUID("01900000-0000-7000-8000-00000000ab42"),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_returns_recipe_view_for_existing_recipe() -> None:
    store = InMemoryEventStore()
    await _seed_recipe(store)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = get_recipe.bind(deps)

    view = await handler(
        GetRecipe(recipe_id=_RECIPE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.recipe.id == _RECIPE_ID
    assert view.recipe.status == RecipeStatus.DEFINED
    # In-memory deps have no pool; timestamps should be None.
    assert view.timestamps is None


@pytest.mark.unit
async def test_handler_returns_none_when_recipe_stream_empty() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = get_recipe.bind(deps)

    view = await handler(
        GetRecipe(recipe_id=_RECIPE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_recipe(store)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = get_recipe.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            GetRecipe(recipe_id=_RECIPE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
