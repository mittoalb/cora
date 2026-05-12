"""Unit tests for the `get_method` query handler.

Mirrors `test_get_capability_handler.py`. Round-trips through the
write side (define → get) verify fold-on-read returns the registered
Method with the right needs_capabilities frozenset.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    Allow,
    AllowAllAuthorize,
    AuthzResult,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.method import (
    Method,
    MethodName,
    MethodStatus,
)
from cora.recipe.features import define_method, get_method
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.get_method import GetMethod

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000ac01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ac02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAP1 = UUID("01900000-0000-7000-8000-000000000111")
_CAP2 = UUID("01900000-0000-7000-8000-000000000222")


def _build_deps(event_store: InMemoryEventStore | None = None) -> Kernel:
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return Kernel(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _EVENT_ID]),
        authorize=AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


@pytest.mark.unit
async def test_handler_returns_method_for_known_id() -> None:
    """Round-trip: define + get."""
    deps = _build_deps()
    await define_method.bind(deps)(
        DefineMethod(name="XRF Fly Mapping", needs_capabilities=frozenset({_CAP1, _CAP2})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_method.bind(deps)
    method = await handler(
        GetMethod(method_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert method == Method(
        id=_NEW_ID,
        name=MethodName("XRF Fly Mapping"),
        needs_capabilities=frozenset({_CAP1, _CAP2}),
        status=MethodStatus.DEFINED,
    )


@pytest.mark.unit
async def test_handler_returns_method_with_empty_needs_capabilities() -> None:
    """Procedural Methods (no equipment requirement) round-trip
    through fold-on-read with empty frozenset preserved."""
    deps = _build_deps()
    await define_method.bind(deps)(
        DefineMethod(name="Sample Cleaning", needs_capabilities=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_method.bind(deps)
    method = await handler(
        GetMethod(method_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert method is not None
    assert method.needs_capabilities == frozenset()


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = _build_deps()
    handler = get_method.bind(deps)
    method = await handler(
        GetMethod(method_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert method is None


class _RecordingAuthorize:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, UUID]] = []

    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
    ) -> AuthzResult:
        self.calls.append((principal_id, command_name, conduit_id))
        return Allow()


class _DenyAllAuthorize:
    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id)
        return Deny(reason="denied for test")


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    tracking = _RecordingAuthorize()
    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _EVENT_ID]),
        authorize=tracking,
        event_store=InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )

    handler = get_method.bind(deps)
    await handler(
        GetMethod(method_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetMethod", UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID]),
        authorize=_DenyAllAuthorize(),
        event_store=InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )

    handler = get_method.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetMethod(method_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_recipe_includes_get_method() -> None:
    deps = _build_deps()
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.get_method)
