"""Unit tests for the Mount projection query helpers' None-pool branch.

The query helpers (`load_mount_id_by_slot_code`,
`load_active_mount_children`, `load_asset_location`) all accept
`pool: asyncpg.Pool | None` and return a benign default (`None` or
empty tuple) when pool is None. This is the test-ergonomics branch:
unit tests can construct handler contexts without a real Postgres.

The happy path (pool is a real asyncpg.Pool) lives at the
integration tier once a Mount slice handler-integration test lands
alongside the slice + integration commits. This file pins ONLY the
None branch so
future refactors do not accidentally swap the None default for a
None-deref crash.
"""

from uuid import uuid4

import pytest

from cora.equipment.projections.asset_location import load_asset_location
from cora.equipment.projections.mount_children import load_active_mount_children
from cora.equipment.projections.mount_lookup import load_mount_id_by_slot_code


@pytest.mark.unit
async def test_load_mount_id_by_slot_code_returns_none_when_pool_is_none() -> None:
    assert await load_mount_id_by_slot_code(None, "02-BM-A-K-01") is None


@pytest.mark.unit
async def test_load_active_mount_children_returns_empty_tuple_when_pool_is_none() -> None:
    result = await load_active_mount_children(None, uuid4())
    assert result == ()


@pytest.mark.unit
async def test_load_asset_location_returns_none_when_pool_is_none() -> None:
    assert await load_asset_location(None, uuid4()) is None
