"""End-to-end integration test: register_asset handler against real Postgres.

Two scenarios cover both genesis paths of the hierarchy rule:
Enterprise root (parent_id=None) and Site-with-parent. Pinned
because the payload's nullable parent_id round-trip through
Postgres jsonb is one of the structural guarantees Asset relies on.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import (
    AssetLevel,
    AssetLifecycle,
    AssetName,
    load_asset,
)
from cora.equipment.features import register_asset
from cora.equipment.features.register_asset import RegisterAsset
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_register_asset_persists_enterprise_root_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Enterprise-level Asset with parent_id=None: payload's null
    serializes through jsonb and the evolver round-trip preserves
    None on read."""
    asset_id = UUID("01900000-0000-7000-8000-00000054ea01")
    event_id = UUID("01900000-0000-7000-8000-00000054ea0e")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, event_id])

    returned_asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="ANL", level=AssetLevel.ENTERPRISE, parent_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_asset_id == asset_id

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 1
    stored = events[0]
    assert stored.event_type == "AssetRegistered"
    assert stored.payload == {
        "asset_id": str(asset_id),
        "name": "ANL",
        "level": "Enterprise",
        "parent_id": None,
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.event_id == event_id

    # Round-trip: load_asset folds back to the expected state.
    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.id == asset_id
    assert state.name == AssetName("ANL")
    assert state.level is AssetLevel.ENTERPRISE
    assert state.parent_id is None
    assert state.lifecycle is AssetLifecycle.COMMISSIONED


@pytest.mark.integration
async def test_register_asset_persists_site_with_parent_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Non-Enterprise Asset with a parent_id: payload's UUID round-
    trips through jsonb as a string and rebuilds via UUID() on read."""
    asset_id = UUID("01900000-0000-7000-8000-00000054eb01")
    event_id = UUID("01900000-0000-7000-8000-00000054eb0e")
    parent_id = UUID("01900000-0000-7000-8000-00000054eb00")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, event_id])

    await register_asset.bind(deps)(
        RegisterAsset(name="APS", level=AssetLevel.SITE, parent_id=parent_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.parent_id == parent_id
    assert state.level is AssetLevel.SITE
    assert state.lifecycle is AssetLifecycle.COMMISSIONED
