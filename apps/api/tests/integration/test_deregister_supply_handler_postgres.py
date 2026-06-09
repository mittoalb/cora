"""End-to-end integration test: deregister_supply handler against real Postgres.

Pins the genesis -> deregister flow on real PG: register_supply
appends SupplyRegistered, then deregister_supply appends
SupplyDeregistered to the same stream at the next version. The
status CHECK constraint must accept the literal `'Decommissioned'`,
exercising the iter-5 schema-widening migration.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.supply.features import deregister_supply, register_supply
from cora.supply.features.deregister_supply import DeregisterSupply
from cora.supply.features.register_supply import RegisterSupply
from tests.integration._helpers import build_postgres_deps

_REGISTER_NOW = datetime(2026, 5, 27, 11, 0, 0, tzinfo=UTC)
_DEREGISTER_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-00000054dc01")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000054dc02")
_TRANSITION_EVENT_ID = UUID("01900000-0000-7000-8000-00000054dc03")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_deregister_supply_appends_transition_event_to_same_stream(
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

    deregister_deps = build_postgres_deps(db_pool, now=_DEREGISTER_NOW, ids=[_TRANSITION_EVENT_ID])
    await deregister_supply.bind(deregister_deps)(
        DeregisterSupply(supply_id=_SUPPLY_ID, reason="typo at registration; re-registering"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deregister_deps.event_store.load("Supply", _SUPPLY_ID)
    assert version == 2
    assert len(events) == 2

    transition = events[1]
    assert transition.event_type == "SupplyDeregistered"
    assert transition.payload == {
        "supply_id": str(_SUPPLY_ID),
        "from_status": "Unknown",
        "reason": "typo at registration; re-registering",
        "trigger": "Operator",
        "triggered_by": str(_PRINCIPAL_ID),
        "occurred_at": _DEREGISTER_NOW.isoformat(),
    }
    assert transition.correlation_id == _CORRELATION_ID
    assert transition.event_id == _TRANSITION_EVENT_ID
    assert transition.metadata == {"command": "DeregisterSupply"}
    assert transition.occurred_at == _DEREGISTER_NOW
    assert transition.principal_id == _PRINCIPAL_ID
