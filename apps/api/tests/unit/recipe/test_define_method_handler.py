"""Unit tests for the `define_method` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.method import InvalidMethodNameError
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000ab01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ab02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAP1 = UUID("01900000-0000-7000-8000-000000000111")
_CAP2 = UUID("01900000-0000-7000-8000-000000000222")


@pytest.mark.unit
async def test_handler_returns_generated_method_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_method.bind(deps)

    result = await handler(
        DefineMethod(name="XRF Mapping", capabilities_needed=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_method_defined_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="XRF Fly Mapping", capabilities_needed=frozenset({_CAP1, _CAP2})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "MethodDefined"
    assert stored.schema_version == 1
    # Payload's capabilities_needed is sorted by string form
    # (deterministic). Compare exact bytes to lock the contract.
    assert stored.payload == {
        "method_id": str(_NEW_ID),
        "name": "XRF Fly Mapping",
        "capabilities_needed": sorted([str(_CAP1), str(_CAP2)]),
        # Phase 10b additive: empty list when MethodDefined has no
        # supplies_needed. Pinned by test_method_supplies_needed.py.
        "supplies_needed": [],
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineMethod"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_handles_empty_capabilities_needed() -> None:
    """Procedural Method (no equipment requirement) lands as
    payload `capabilities_needed = []`."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="Sample Cleaning", capabilities_needed=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["capabilities_needed"] == []


@pytest.mark.unit
async def test_handler_trims_method_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="  XRF Mapping  ", capabilities_needed=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["name"] == "XRF Mapping"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, deny=True)
    handler = define_method.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DefineMethod(name="X", capabilities_needed=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = define_method.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DefineMethod(name="X", capabilities_needed=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Method", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_method_name_error() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_method.bind(deps)

    with pytest.raises(InvalidMethodNameError):
        await handler(
            DefineMethod(name="   ", capabilities_needed=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="X", capabilities_needed=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_recipe_returns_handlers_bundle() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.define_method)
    assert callable(handlers.get_method)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end: causation_id survives `with_tracing(with_idempotency(bare))`."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handlers = wire_recipe(deps)

    await handlers.define_method(
        DefineMethod(name="X", capabilities_needed=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].causation_id == causation
