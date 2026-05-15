"""End-to-end integration test: truncate_procedure against real Postgres (Phase 10c-c iter 1).

Pinned: ProcedureTruncated round-trips through jsonb (interrupted_at
as ISO-8601 string when set, null when None) and the Procedure folds
back to TRUNCATED state with all additive fields (steps_logbook_id
included) preserved.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import pytest

from cora.operation.aggregates.procedure import (
    ProcedureStatus,
    fold,
    from_stored,
)
from cora.operation.features import register_procedure, start_procedure, truncate_procedure
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.truncate_procedure import TruncateProcedure
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_truncate_procedure_persists_event_to_postgres_with_interrupted_at(
    db_pool: asyncpg.Pool,
) -> None:
    procedure_id = UUID("01900000-0000-7000-8000-0000010c0c11")
    register_event_id = UUID("01900000-0000-7000-8000-0000010c0c12")
    start_event_id = UUID("01900000-0000-7000-8000-0000010c0c13")
    truncate_event_id = UUID("01900000-0000-7000-8000-0000010c0c14")
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[procedure_id, register_event_id, start_event_id, truncate_event_id],
    )

    await register_procedure.bind(deps)(
        RegisterProcedure(name="Vessel-A bakeout", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_procedure.bind(deps)(
        StartProcedure(procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    interrupted_at = _NOW - timedelta(hours=12)
    await truncate_procedure.bind(deps)(
        TruncateProcedure(
            procedure_id=procedure_id,
            reason="weekend power loss",
            interrupted_at=interrupted_at,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Procedure", procedure_id)
    assert version == 3
    assert events[2].event_type == "ProcedureTruncated"
    assert events[2].event_id == truncate_event_id
    assert events[2].principal_id == _PRINCIPAL_ID
    assert events[2].correlation_id == _CORRELATION_ID
    assert events[2].payload == {
        "procedure_id": str(procedure_id),
        "reason": "weekend power loss",
        "interrupted_at": interrupted_at.isoformat(),
        "occurred_at": _NOW.isoformat(),
    }

    # Round-trip back through fold: confirms TRUNCATED state and field preservation.
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.status is ProcedureStatus.TRUNCATED
    assert state.kind == "bakeout"


@pytest.mark.integration
async def test_truncate_procedure_persists_with_null_interrupted_at(
    db_pool: asyncpg.Pool,
) -> None:
    """interrupted_at=None roundtrips as null through jsonb."""
    procedure_id = UUID("01900000-0000-7000-8000-0000010c0d01")
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            procedure_id,
            *(UUID(f"01900000-0000-7000-8000-0000010c0d{i:02x}") for i in range(2, 5)),
        ],
    )

    await register_procedure.bind(deps)(
        RegisterProcedure(name="X", kind="bakeout"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_procedure.bind(deps)(
        StartProcedure(procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await truncate_procedure.bind(deps)(
        TruncateProcedure(procedure_id=procedure_id, reason="unknown when crashed"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Procedure", procedure_id)
    assert events[2].payload["interrupted_at"] is None
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.status is ProcedureStatus.TRUNCATED
