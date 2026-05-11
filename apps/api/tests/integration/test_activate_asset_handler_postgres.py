"""End-to-end integration test: activate_asset handler against real Postgres."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetLevel
from cora.equipment.features import activate_asset, register_asset
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.postgres.idempotency import PostgresIdempotencyStore

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000054ec01")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ec0e")
_ACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ec0f")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000054ec00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_activate_asset_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID, _REGISTER_EVENT_ID, _ACTIVATE_EVENT_ID]),
        authorize=AllowAllAuthorize(),
        event_store=PostgresEventStore(db_pool),
        idempotency_store=PostgresIdempotencyStore(db_pool),
    )

    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", level=AssetLevel.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert asset_id == _NEW_ID

    await activate_asset.bind(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 2
    activated = events[1]
    assert activated.event_type == "AssetActivated"
    assert activated.payload == {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert activated.event_id == _ACTIVATE_EVENT_ID
    assert activated.metadata == {"command": "ActivateAsset"}
