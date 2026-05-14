"""Unit tests for the `define_practice` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.practice import InvalidPracticeNameError
from cora.recipe.features import define_practice
from cora.recipe.features.define_practice import DefinePractice
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000bb01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000bb02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000000111")
_SITE_ID = UUID("01900000-0000-7000-8000-000000000222")


@pytest.mark.unit
async def test_handler_returns_generated_practice_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_practice.bind(deps)

    result = await handler(
        DefinePractice(name="X", method_id=_METHOD_ID, site_id=_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_practice_defined_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_practice.bind(deps)

    await handler(
        DefinePractice(
            name="APS Standard Tomography",
            method_id=_METHOD_ID,
            site_id=_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Practice", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "PracticeDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "practice_id": str(_NEW_ID),
        "name": "APS Standard Tomography",
        "method_id": str(_METHOD_ID),
        "site_id": str(_SITE_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefinePractice"}


@pytest.mark.unit
async def test_handler_trims_practice_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_practice.bind(deps)

    await handler(
        DefinePractice(name="  X  ", method_id=_METHOD_ID, site_id=_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Practice", _NEW_ID)
    assert events[0].payload["name"] == "X"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, deny=True)
    handler = define_practice.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DefinePractice(name="X", method_id=_METHOD_ID, site_id=_SITE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = define_practice.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DefinePractice(name="X", method_id=_METHOD_ID, site_id=_SITE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Practice", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_practice_name_error() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_practice.bind(deps)

    with pytest.raises(InvalidPracticeNameError):
        await handler(
            DefinePractice(name="   ", method_id=_METHOD_ID, site_id=_SITE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_practice.bind(deps)

    await handler(
        DefinePractice(name="X", method_id=_METHOD_ID, site_id=_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Practice", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_recipe_returns_handlers_bundle_with_practice() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.define_practice)
    assert callable(handlers.get_practice)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end: causation_id survives `with_tracing(with_idempotency(bare))`."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handlers = wire_recipe(deps)

    await handlers.define_practice(
        DefinePractice(name="X", method_id=_METHOD_ID, site_id=_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Practice", _NEW_ID)
    assert events[0].causation_id == causation
