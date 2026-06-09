"""End-to-end integration test: register_supply handler against real Postgres."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.supply.aggregates.supply import SupplyScope
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000054ca81")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ca8e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_register_supply_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])

    supply_id = await register_supply.bind(deps)(
        RegisterSupply(
            scope=SupplyScope.BEAMLINE,
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert supply_id == _NEW_ID

    events, version = await deps.event_store.load("Supply", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "SupplyRegistered"
    assert stored.schema_version == 1
    assert stored.payload == {
        "supply_id": str(_NEW_ID),
        "scope": "Beamline",
        "kind": "LiquidNitrogen",
        "name": "2-BM LN2",
        "facility_code": "cora",
        "trigger": "Operator",
        "triggered_by": str(_PRINCIPAL_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterSupply"}
    assert stored.occurred_at == _NOW
    assert stored.principal_id == _PRINCIPAL_ID
