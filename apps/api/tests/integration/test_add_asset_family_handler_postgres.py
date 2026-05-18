"""End-to-end integration test: add_asset_family against real Postgres.

Pin: payload round-trips through jsonb with family_id as a UUID
string; the evolver reconstructs into the frozenset on next load.
Two scenarios — adding a single capability, then verifying that
load+fold returns a state with the capability in the set.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetLevel, load_asset
from cora.equipment.features import add_asset_family, register_asset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.register_asset import RegisterAsset
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-00000056fa00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_add_asset_family_persists_event_and_round_trips_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = UUID("01900000-0000-7000-8000-00000056fa01")
    register_event_id = UUID("01900000-0000-7000-8000-00000056fa0e")
    add_event_id = UUID("01900000-0000-7000-8000-00000056fa0f")
    cap1 = UUID("01900000-0000-7000-8000-000000000111")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[asset_id, register_event_id, add_event_id])

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetFamilyAdded",
    ]
    added = events[1]
    assert added.event_id == add_event_id
    assert added.metadata == {"command": "AddAssetFamily"}
    assert added.payload["family_id"] == str(cap1)

    # Fold-on-read reconstructs the capabilities frozenset.
    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.families == frozenset({cap1})
