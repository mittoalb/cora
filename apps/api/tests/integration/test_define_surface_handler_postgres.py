"""End-to-end integration test: define_surface handler against real Postgres.

Mirrors `test_define_zone_handler_postgres.py` for the
Surface aggregate. Proves the bare handler composes with
PostgresEventStore: SurfaceKind enum string round-trips through
jsonb, the event lands under stream_type='Surface', the payload
matches the locked shape byte-for-byte.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.trust.aggregates.surface import SurfaceKind
from cora.trust.features import define_surface
from cora.trust.features.define_surface import DefineSurface
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000c500")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d500")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_handler_persists_surface_defined_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])
    handler = define_surface.bind(deps)

    surface_id = await handler(
        DefineSurface(name="System HTTP", kind=SurfaceKind.HTTP),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert surface_id == _NEW_ID

    events, version = await deps.event_store.load("Surface", _NEW_ID)
    assert version == 1
    assert len(events) == 1

    stored = events[0]
    assert stored.event_type == "SurfaceDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "surface_id": str(_NEW_ID),
        "name": "System HTTP",
        "kind": "http",
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineSurface"}
    assert stored.occurred_at == _NOW
    assert stored.position > 0


@pytest.mark.integration
async def test_handler_persists_mcp_streamable_http_kind_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin that each closed-enum kind round-trips through jsonb."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])
    handler = define_surface.bind(deps)

    await handler(
        DefineSurface(name="System MCP streamable-http", kind=SurfaceKind.MCP_STREAMABLE_HTTP),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Surface", _NEW_ID)
    assert events[0].payload["kind"] == "mcp_streamable_http"
