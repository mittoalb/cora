"""Unit tests for the `define_surface` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.trust import TrustHandlers, UnauthorizedError, wire_trust
from cora.trust.aggregates.surface import InvalidSurfaceNameError, SurfaceKind
from cora.trust.features import define_surface
from cora.trust.features.define_surface import DefineSurface
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000401")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000004e1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _command(name: str = "System HTTP", kind: SurfaceKind = SurfaceKind.HTTP) -> DefineSurface:
    return DefineSurface(name=name, kind=kind)


@pytest.mark.unit
async def test_handler_returns_generated_surface_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_surface.bind(deps)

    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_surface_defined_event() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_surface.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Surface", _NEW_ID)
    assert version == 1
    assert [e.event_type for e in events] == ["SurfaceDefined"]
    defined = events[0]
    assert defined.payload == {
        "surface_id": str(_NEW_ID),
        "name": "System HTTP",
        "kind": "http",
        "occurred_at": _NOW.isoformat(),
    }
    assert defined.correlation_id == _CORRELATION_ID
    assert defined.principal_id == _PRINCIPAL_ID
    assert defined.metadata == {"command": "DefineSurface"}


@pytest.mark.unit
async def test_handler_persists_mcp_stdio_kind() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_surface.bind(deps)

    await handler(
        _command(name="System MCP stdio", kind=SurfaceKind.MCP_STDIO),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Surface", _NEW_ID)
    assert events[0].payload["kind"] == "mcp_stdio"


@pytest.mark.unit
async def test_handler_persists_mcp_streamable_http_kind() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_surface.bind(deps)

    await handler(
        _command(name="System MCP streamable-http", kind=SurfaceKind.MCP_STREAMABLE_HTTP),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Surface", _NEW_ID)
    assert events[0].payload["kind"] == "mcp_streamable_http"


@pytest.mark.unit
async def test_handler_rejects_whitespace_only_name() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_surface.bind(deps)

    with pytest.raises(InvalidSurfaceNameError):
        await handler(
            _command(name="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_when_authz_denies() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, deny=True)
    handler = define_surface.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_trust_includes_define_surface_and_get_surface() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_trust(deps)
    assert isinstance(handlers, TrustHandlers)
    assert callable(handlers.define_surface)
    assert callable(handlers.get_surface)
