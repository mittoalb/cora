"""Unit tests for the `get_method` query handler.

Mirrors `test_get_capability_handler.py`. Round-trips through the
write side (define → get) verify fold-on-read returns the registered
Method with the right needs_capabilities frozenset.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports import (
    Allow,
    AuthzResult,
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
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000ac01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ac02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAP1 = UUID("01900000-0000-7000-8000-000000000111")
_CAP2 = UUID("01900000-0000-7000-8000-000000000222")


@pytest.mark.unit
async def test_handler_returns_method_for_known_id() -> None:
    """Round-trip: define + get."""
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
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
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
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
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
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


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    tracking = _RecordingAuthorize()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, authorize=tracking)

    handler = get_method.bind(deps)
    await handler(
        GetMethod(method_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetMethod", UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_NEW_ID], now=_NOW, deny=True)

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
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.get_method)
