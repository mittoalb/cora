"""Unit tests for the `define_method` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    AuthzResult,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.method import InvalidMethodNameError
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000ab01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ab02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAP1 = UUID("01900000-0000-7000-8000-000000000111")
_CAP2 = UUID("01900000-0000-7000-8000-000000000222")


class DenyAllAuthorize:
    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id)
        return Deny(reason="denied for test")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> SharedDeps:
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return SharedDeps(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _EVENT_ID]),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


@pytest.mark.unit
async def test_handler_returns_generated_method_id() -> None:
    deps = _build_deps()
    handler = define_method.bind(deps)

    result = await handler(
        DefineMethod(name="XRF Mapping", needs_capabilities=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_method_defined_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="XRF Fly Mapping", needs_capabilities=frozenset({_CAP1, _CAP2})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "MethodDefined"
    assert stored.schema_version == 1
    # Payload's needs_capabilities is sorted by string form
    # (deterministic). Compare exact bytes to lock the contract.
    assert stored.payload == {
        "method_id": str(_NEW_ID),
        "name": "XRF Fly Mapping",
        "needs_capabilities": sorted([str(_CAP1), str(_CAP2)]),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineMethod"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_handles_empty_needs_capabilities() -> None:
    """Procedural Method (no equipment requirement) lands as
    payload `needs_capabilities = []`."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="Sample Cleaning", needs_capabilities=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["needs_capabilities"] == []


@pytest.mark.unit
async def test_handler_trims_method_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="  XRF Mapping  ", needs_capabilities=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].payload["name"] == "XRF Mapping"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = define_method.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            DefineMethod(name="X", needs_capabilities=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_method.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DefineMethod(name="X", needs_capabilities=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Method", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_method_name_error() -> None:
    deps = _build_deps()
    handler = define_method.bind(deps)

    with pytest.raises(InvalidMethodNameError):
        await handler(
            DefineMethod(name="   ", needs_capabilities=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_method.bind(deps)

    await handler(
        DefineMethod(name="X", needs_capabilities=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_recipe_returns_handlers_bundle() -> None:
    deps = _build_deps()
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.define_method)
    assert callable(handlers.get_method)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end: causation_id survives `with_tracing(with_idempotency(bare))`."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handlers = wire_recipe(deps)

    await handlers.define_method(
        DefineMethod(name="X", needs_capabilities=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Method", _NEW_ID)
    assert events[0].causation_id == causation
