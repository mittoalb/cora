"""Integration test: get_family handler against real Postgres."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.family import FamilyName, FamilyStatus
from cora.equipment.features import define_family, get_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.get_family import GetFamily
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000054cb01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb0e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_get_family_loads_state_from_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_CAPABILITY_ID, _EVENT_ID])

    await define_family.bind(deps)(
        DefineFamily(name="X-ray Fluorescence Mapping"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    capability = await get_family.bind(deps)(
        GetFamily(family_id=_CAPABILITY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert capability is not None
    assert capability.id == _CAPABILITY_ID
    assert capability.name == FamilyName("X-ray Fluorescence Mapping")
    assert capability.status is FamilyStatus.DEFINED
