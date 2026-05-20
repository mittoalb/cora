"""Unit tests for the `get_surface` query handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.trust import UnauthorizedError
from cora.trust.aggregates.surface import (
    SurfaceDefined,
    SurfaceKind,
    SurfaceStatus,
    event_type_name,
    to_payload,
)
from cora.trust.features import get_surface
from cora.trust.features.get_surface import GetSurface
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
_SURFACE_ID = UUID("01900000-0000-7000-8000-000000000501")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_surface(
    store: InMemoryEventStore,
    *,
    surface_id: UUID = _SURFACE_ID,
    name: str = "System HTTP",
    kind: SurfaceKind = SurfaceKind.HTTP,
) -> None:
    event = SurfaceDefined(surface_id=surface_id, name=name, kind=kind, occurred_at=_NOW)
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="DefineSurface",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    await store.append("Surface", surface_id, expected_version=0, events=[new_event])


@pytest.mark.unit
async def test_handler_returns_none_when_surface_missing() -> None:
    deps = build_deps(ids=[uuid4() for _ in range(4)], now=_NOW)
    handler = get_surface.bind(deps)

    result = await handler(
        GetSurface(surface_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_returns_folded_surface_when_seeded() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(4)], now=_NOW, event_store=store)
    await _seed_surface(store)
    handler = get_surface.bind(deps)

    result = await handler(
        GetSurface(surface_id=_SURFACE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.id == _SURFACE_ID
    assert result.name.value == "System HTTP"
    assert result.kind == SurfaceKind.HTTP
    assert result.status == SurfaceStatus.DEFINED
    # Lifecycle timestamps removed from Surface state per Iter D (Path C
    # carve-out for singleton aggregate); see surface/state.py docstring.


@pytest.mark.unit
async def test_handler_raises_unauthorized_when_authz_denies() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(4)], now=_NOW, event_store=store, deny=True)
    await _seed_surface(store)
    handler = get_surface.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            GetSurface(surface_id=_SURFACE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
