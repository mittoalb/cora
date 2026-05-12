"""End-to-end integration test: remove_asset_capability against real Postgres.

Round-trip: register + add + remove leaves the asset back at empty
capabilities (verified via load_asset fold-on-read).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetLevel, load_asset
from cora.equipment.features import (
    add_asset_capability,
    register_asset,
    remove_asset_capability,
)
from cora.equipment.features.add_asset_capability import AddAssetCapability
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.remove_asset_capability import RemoveAssetCapability
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-00000056fb00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_remove_asset_capability_persists_event_and_drops_from_fold(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = UUID("01900000-0000-7000-8000-00000056fb01")
    register_event_id = UUID("01900000-0000-7000-8000-00000056fb0e")
    add_event_id = UUID("01900000-0000-7000-8000-00000056fb0f")
    remove_event_id = UUID("01900000-0000-7000-8000-00000056fb10")
    cap1 = UUID("01900000-0000-7000-8000-000000000222")

    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([asset_id, register_event_id, add_event_id, remove_event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_capability.bind(deps)(
        AddAssetCapability(asset_id=asset_id, capability_id=cap1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_asset_capability.bind(deps)(
        RemoveAssetCapability(asset_id=asset_id, capability_id=cap1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetCapabilityAdded",
        "AssetCapabilityRemoved",
    ]
    removed = events[2]
    assert removed.event_id == remove_event_id
    assert removed.metadata == {"command": "RemoveAssetCapability"}

    # Fold-on-read reconstructs the empty frozenset.
    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.capabilities == frozenset()
