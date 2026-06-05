"""End-to-end integration test: full Supply FSM cycle against real Postgres (10a-b).

Walks the entire 5-state FSM through real PG event store via slice handlers:

    register_supply        -> Unknown
    mark_supply_available  -> Available
    degrade_supply         -> Degraded
    mark_supply_unavailable -> Unavailable
    mark_supply_recovering -> Recovering
    restore_supply         -> Available

Verifies the persisted stream is exactly 6 events at version 6, the event
types are in cycle order, and the audit triple (`from_status`, `reason`,
`trigger`) on each transition event matches the slice that emitted it.

This is the cross-slice end-to-end pin for 10a-b: per-slice integration
tests for `register_supply` and `mark_supply_available` already exist;
this one proves the four new transition slices append correctly when
chained on a single stream against real PG.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.supply.aggregates.supply import SupplyScope
from cora.supply.features import (
    degrade_supply,
    mark_supply_available,
    mark_supply_recovering,
    mark_supply_unavailable,
    register_supply,
    restore_supply,
)
from cora.supply.features.degrade_supply import DegradeSupply
from cora.supply.features.mark_supply_available import MarkSupplyAvailable
from cora.supply.features.mark_supply_recovering import MarkSupplyRecovering
from cora.supply.features.mark_supply_unavailable import MarkSupplyUnavailable
from cora.supply.features.register_supply import RegisterSupply
from cora.supply.features.restore_supply import RestoreSupply
from tests.integration._helpers import build_postgres_deps

_T0 = datetime(2026, 5, 14, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 14, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 5, 14, 13, 0, 0, tzinfo=UTC)
_T4 = datetime(2026, 5, 14, 14, 0, 0, tzinfo=UTC)
_T5 = datetime(2026, 5, 14, 15, 0, 0, tzinfo=UTC)

_SUPPLY_ID = UUID("01900000-0000-7000-8000-00000054fc01")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000054fc02")
_AVAILABLE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054fc03")
_DEGRADED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054fc04")
_UNAVAILABLE_EVENT_ID = UUID("01900000-0000-7000-8000-00000054fc05")
_RECOVERING_EVENT_ID = UUID("01900000-0000-7000-8000-00000054fc06")
_RESTORED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054fc07")

_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_full_supply_fsm_cycle_appends_six_events_to_one_stream(
    db_pool: asyncpg.Pool,
) -> None:
    register_deps = build_postgres_deps(db_pool, now=_T0, ids=[_SUPPLY_ID, _GENESIS_EVENT_ID])
    supply_id = await register_supply.bind(register_deps)(
        RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="2-BM LN2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert supply_id == _SUPPLY_ID

    await mark_supply_available.bind(
        build_postgres_deps(db_pool, now=_T1, ids=[_AVAILABLE_EVENT_ID])
    )(
        MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="walkdown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await degrade_supply.bind(build_postgres_deps(db_pool, now=_T2, ids=[_DEGRADED_EVENT_ID]))(
        DegradeSupply(supply_id=_SUPPLY_ID, reason="half-current"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await mark_supply_unavailable.bind(
        build_postgres_deps(db_pool, now=_T3, ids=[_UNAVAILABLE_EVENT_ID])
    )(
        MarkSupplyUnavailable(supply_id=_SUPPLY_ID, reason="full dump"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await mark_supply_recovering.bind(
        build_postgres_deps(db_pool, now=_T4, ids=[_RECOVERING_EVENT_ID])
    )(
        MarkSupplyRecovering(supply_id=_SUPPLY_ID, reason="beam returning"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    final_deps = build_postgres_deps(db_pool, now=_T5, ids=[_RESTORED_EVENT_ID])
    await restore_supply.bind(final_deps)(
        RestoreSupply(supply_id=_SUPPLY_ID, reason="ops confirms stable"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await final_deps.event_store.load("Supply", _SUPPLY_ID)
    assert version == 6
    assert len(events) == 6
    assert [e.event_type for e in events] == [
        "SupplyRegistered",
        "SupplyMarkedAvailable",
        "SupplyDegraded",
        "SupplyMarkedUnavailable",
        "SupplyMarkedRecovering",
        "SupplyRestored",
    ]

    transitions = events[1:]
    expected_from_statuses = ["Unknown", "Available", "Degraded", "Unavailable", "Recovering"]
    expected_reasons = [
        "walkdown",
        "half-current",
        "full dump",
        "beam returning",
        "ops confirms stable",
    ]
    for transition, expected_from, expected_reason in zip(
        transitions, expected_from_statuses, expected_reasons, strict=True
    ):
        assert transition.payload["from_status"] == expected_from
        assert transition.payload["reason"] == expected_reason
        assert transition.payload["trigger"] == "Operator"
        assert transition.principal_id == _PRINCIPAL_ID
        assert transition.correlation_id == _CORRELATION_ID
