"""Integration test: get_asset handler against real Postgres.

Two scenarios pin the fold-on-read path against the real event
store: a fresh registration (genesis-only stream) and a registered +
relocated asset (multi-event stream where the read must reflect the
mutated parent_id, not the registration payload).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import (
    AssetLevel,
    AssetLifecycle,
    AssetName,
)
from cora.equipment.features import get_asset, register_asset, relocate_asset
from cora.equipment.features.get_asset import GetAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.relocate_asset import RelocateAsset
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
_PARENT_ID = UUID("01900000-0000-7000-8000-00000054fa00")
_NEW_PARENT_ID = UUID("01900000-0000-7000-8000-00000054fa01")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_asset_loads_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = UUID("01900000-0000-7000-8000-00000054fa02")
    register_event_id = UUID("01900000-0000-7000-8000-00000054fa0e")

    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([asset_id, register_event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    asset = await get_asset.bind(deps)(
        GetAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert asset is not None
    assert asset.id == asset_id
    assert asset.name == AssetName("APS-2BM")
    assert asset.level is AssetLevel.UNIT
    assert asset.parent_id == _PARENT_ID
    assert asset.lifecycle is AssetLifecycle.COMMISSIONED


@pytest.mark.integration
async def test_get_asset_reflects_relocate_against_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Multi-event stream: register + relocate → read returns mutated
    parent_id. Pinned because the AssetRelocated evolver arm has to
    fire during fold-on-read, not just at write time."""
    asset_id = UUID("01900000-0000-7000-8000-00000054fb01")
    register_event_id = UUID("01900000-0000-7000-8000-00000054fb0e")
    relocate_event_id = UUID("01900000-0000-7000-8000-00000054fb0f")

    deps = Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([asset_id, register_event_id, relocate_event_id]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await relocate_asset.bind(deps)(
        RelocateAsset(
            asset_id=asset_id,
            to_parent_id=_NEW_PARENT_ID,
            reason="moved",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    asset = await get_asset.bind(deps)(
        GetAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert asset is not None
    assert asset.parent_id == _NEW_PARENT_ID
    assert asset.lifecycle is AssetLifecycle.COMMISSIONED
