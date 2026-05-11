"""Unit tests for the `deprecate_method` application handler.

Mirror of `test_deprecate_capability_handler.py` (Equipment 5f-2).
"""

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
from cora.recipe.aggregates.method import (
    MethodCannotDeprecateError,
    MethodNotFoundError,
)
from cora.recipe.features import define_method, deprecate_method, version_method
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.deprecate_method import DeprecateMethod
from cora.recipe.features.version_method import VersionMethod

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_METHOD_ID = UUID("01900000-0000-7000-8000-00000000ae01")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ae02")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ae03")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ae04")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


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
        id_generator=FixedIdGenerator(
            [_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID]
        ),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


async def _define_method_helper(deps: SharedDeps) -> UUID:
    return await define_method.bind(deps)(
        DefineMethod(name="XRF Mapping", needs_capabilities=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    method_id = await _define_method_helper(deps)

    result = await deprecate_method.bind(deps)(
        DeprecateMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_method_deprecated_event_from_defined() -> None:
    """Direct deprecation (no prior version)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    method_id = await _define_method_helper(deps)

    await deprecate_method.bind(deps)(
        DeprecateMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", method_id)
    assert version == 2
    assert [e.event_type for e in events] == ["MethodDefined", "MethodDeprecated"]
    deprecated = events[1]
    # FixedIdGenerator: defining consumed _METHOD_ID + _DEFINED_EVENT_ID,
    # then deprecate consumed _VERSIONED_EVENT_ID (intended for version,
    # but skipped here).
    assert deprecated.event_id == _VERSIONED_EVENT_ID
    assert deprecated.metadata == {"command": "DeprecateMethod"}


@pytest.mark.unit
async def test_handler_appends_method_deprecated_event_from_versioned() -> None:
    """Full lifecycle: define → version → deprecate."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    method_id = await _define_method_helper(deps)

    await version_method.bind(deps)(
        VersionMethod(method_id=method_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_method.bind(deps)(
        DeprecateMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", method_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "MethodDefined",
        "MethodVersioned",
        "MethodDeprecated",
    ]
    deprecated = events[2]
    assert deprecated.event_id == _DEPRECATED_EVENT_ID


@pytest.mark.unit
async def test_handler_raises_method_not_found_when_method_does_not_exist() -> None:
    deps = _build_deps()
    handler = deprecate_method.bind(deps)

    with pytest.raises(MethodNotFoundError):
        await handler(
            DeprecateMethod(method_id=_METHOD_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    method_id = await _define_method_helper(deps)

    handler = deprecate_method.bind(deps)
    await handler(
        DeprecateMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(MethodCannotDeprecateError):
        await handler(
            DeprecateMethod(method_id=method_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    method_id = await _define_method_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await deprecate_method.bind(deny_deps)(
            DeprecateMethod(method_id=method_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    method_id = await _define_method_helper(deps)

    await deprecate_method.bind(deps)(
        DeprecateMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Method", method_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_recipe_includes_deprecate_method() -> None:
    deps = _build_deps()
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.deprecate_method)
