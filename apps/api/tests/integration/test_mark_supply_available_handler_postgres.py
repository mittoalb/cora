"""End-to-end integration test: mark_supply_available handler against real Postgres.

Pins the genesis -> transition flow on real PG: register_supply
appends SupplyRegistered, then mark_supply_available appends
SupplyMarkedAvailable to the same stream at the next version.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.supply.features import mark_supply_available, register_supply
from cora.supply.features.mark_supply_available import MarkSupplyAvailable
from cora.supply.features.register_supply import RegisterSupply
from tests.integration._helpers import build_postgres_deps

_REGISTER_NOW = datetime(2026, 5, 14, 11, 0, 0, tzinfo=UTC)
_MARK_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-00000054cb01")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb02")
_TRANSITION_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb03")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_mark_supply_available_appends_transition_event_to_same_stream(
    db_pool: asyncpg.Pool,
) -> None:
    register_deps = build_postgres_deps(
        db_pool, now=_REGISTER_NOW, ids=[_SUPPLY_ID, _GENESIS_EVENT_ID]
    )
    supply_id = await register_supply.bind(register_deps)(
        RegisterSupply(
            kind="LiquidNitrogen",
            name="2-BM LN2",
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert supply_id == _SUPPLY_ID

    mark_deps = build_postgres_deps(db_pool, now=_MARK_NOW, ids=[_TRANSITION_EVENT_ID])
    await mark_supply_available.bind(mark_deps)(
        MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="operator walkdown confirms LN2 flowing"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await mark_deps.event_store.load("Supply", _SUPPLY_ID)
    assert version == 2
    assert len(events) == 2

    transition = events[1]
    assert transition.event_type == "SupplyMarkedAvailable"
    assert transition.payload == {
        "supply_id": str(_SUPPLY_ID),
        "from_status": "Unknown",
        "reason": "operator walkdown confirms LN2 flowing",
        "trigger": "Operator",
        "triggered_by": str(_PRINCIPAL_ID),
        "occurred_at": _MARK_NOW.isoformat(),
    }
    assert transition.correlation_id == _CORRELATION_ID
    assert transition.event_id == _TRANSITION_EVENT_ID
    assert transition.metadata == {"command": "MarkSupplyAvailable"}
    assert transition.occurred_at == _MARK_NOW
    assert transition.principal_id == _PRINCIPAL_ID
