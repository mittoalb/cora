"""End-to-end integration test: register_clearance handler against real Postgres."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.safety.aggregates.clearance import (
    ClearanceKind,
    HazardDeclaration,
    RunBinding,
    SubjectBinding,
    load_clearance,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.features import get_clearance, register_clearance
from cora.safety.features.get_clearance import GetClearance
from cora.safety.features.register_clearance import RegisterClearance
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000055ca81")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000055ca8e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_register_clearance_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])
    rid = uuid4()

    clearance_id = await register_clearance.bind(deps)(
        RegisterClearance(
            kind=ClearanceKind.ESAF,
            facility_code="cora",
            title="Pilot ESAF for 2-BM",
            bindings=frozenset({RunBinding(run_id=rid)}),
            risk_band=RiskBand.YELLOW,
            external_id="ESAF-12345",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert clearance_id == _NEW_ID

    events, version = await deps.event_store.load("Clearance", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ClearanceRegistered"
    assert stored.schema_version == 1
    assert stored.payload["clearance_id"] == str(_NEW_ID)
    assert stored.payload["kind"] == "ESAF"
    assert stored.payload["title"] == "Pilot ESAF for 2-BM"
    assert stored.payload["bindings"] == [{"kind": "Run", "id": str(rid)}]
    assert stored.payload["risk_band"] == "Yellow"
    assert stored.payload["external_id"] == "ESAF-12345"
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterClearance"}
    assert stored.occurred_at == _NOW
    assert stored.principal_id == _PRINCIPAL_ID


@pytest.mark.integration
async def test_register_then_get_clearance_round_trip_via_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Round-trip: register a clearance, then fetch it back via get_clearance.
    Pins both sides of the lazy-load + fold cycle against real Postgres."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])
    sid = uuid4()
    rid = uuid4()

    clearance_id = await register_clearance.bind(deps)(
        RegisterClearance(
            kind=ClearanceKind.SAF,
            facility_code="cora",
            title="NSLS-II SAF roundtrip",
            bindings=frozenset({SubjectBinding(subject_id=sid), RunBinding(run_id=rid)}),
            declarations=frozenset(
                {
                    HazardDeclaration(
                        target=SubjectBinding(subject_id=sid),
                        classifications=frozenset({RiskBand.GREEN}),
                        mitigations=frozenset({"ppe:safety_glasses"}),
                        notes="benign sample",
                    )
                }
            ),
            risk_band=RiskBand.GREEN,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    state = await get_clearance.bind(deps)(
        GetClearance(clearance_id=clearance_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert state is not None
    assert state.id == clearance_id
    assert state.kind == ClearanceKind.SAF
    assert state.title.value == "NSLS-II SAF roundtrip"
    assert state.risk_band == RiskBand.GREEN
    assert SubjectBinding(subject_id=sid) in state.bindings
    assert RunBinding(run_id=rid) in state.bindings
    assert len(state.declarations) == 1


@pytest.mark.integration
async def test_load_clearance_returns_none_for_unknown_id(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])
    state = await load_clearance(deps.event_store, uuid4())
    assert state is None
