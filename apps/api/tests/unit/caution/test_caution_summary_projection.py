"""Unit tests for CautionSummaryProjection.

Pins per-event-type apply() dispatch for the 3 subscribed Caution
events. Postgres-side behavior (CHECK constraints, GIN index round-
trips, drain) is in the integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from cora.caution.projections import CautionSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent


def _conn_with_savepoint() -> AsyncMock:
    """AsyncMock conn whose `transaction()` returns an async context manager.

    The projection's `CautionRegistered` arm wraps its INSERT in
    `async with conn.transaction(): ...` so any future cross-stream
    uniqueness violation rolls back only the inner SAVEPOINT (not the
    worker's outer batch txn). The unit test mock needs to satisfy
    that protocol shape (mirrors the supply projection's test idiom).
    """
    conn = AsyncMock()
    transaction_cm = AsyncMock()
    transaction_cm.__aenter__.return_value = None
    transaction_cm.__aexit__.return_value = None
    conn.transaction = MagicMock(return_value=transaction_cm)
    return conn


_CAUTION_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_PRINCIPAL_ID = uuid4()
_AUTHOR_ID = uuid4()
_ASSET_ID = uuid4()
_PROCEDURE_ID = uuid4()
_PARENT_CAUTION_ID = uuid4()
_BY_CAUTION_ID = uuid4()
_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Caution",
        stream_id=_CAUTION_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _registered_payload(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "caution_id": str(_CAUTION_ID),
        "target": {"kind": "Asset", "id": str(_ASSET_ID)},
        "category": "Wear",
        "severity": "Caution",
        "text": "hexapod stalls below 0.5 mm/s",
        "workaround": "run at 0.6 mm/s",
        "tags": ["alpha", "mu", "zeta"],
        "author_actor_id": str(_AUTHOR_ID),
        "expires_at": None,
        "propagate_to_children": False,
        "parent_caution_id": None,
        "occurred_at": _NOW.isoformat(),
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = CautionSummaryProjection()
    assert proj.name == "proj_caution_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "CautionRegistered",
            "CautionSuperseded",
            "CautionRetired",
        }
    )


@pytest.mark.unit
def test_projection_does_not_subscribe_to_unrelated_events() -> None:
    """Foreign event types belong to other projections."""
    proj = CautionSummaryProjection()
    for foreign in (
        "AssetRegistered",
        "SupplyRegistered",
        "ClearanceRegistered",
        "RunStarted",
    ):
        assert foreign not in proj.subscribed_event_types


@pytest.mark.unit
async def test_caution_registered_inserts_with_active_status_and_null_audit() -> None:
    proj = CautionSummaryProjection()
    conn = _conn_with_savepoint()
    event = _stored("CautionRegistered", _registered_payload())

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    conn.transaction.assert_called_once()  # SAVEPOINT engaged for the INSERT
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_caution_summary" in sql
    assert "ON CONFLICT (caution_id) DO NOTHING" in sql
    assert "'Active'" in sql  # status literal
    # Bound parameters (positional):
    #   $1 caution_id, $2 target_kind, $3 target_id, $4 category,
    #   $5 severity, $6 text, $7 workaround, $8 author_actor_id,
    #   $9 tags, $10 expires_at, $11 propagate_to_children,
    #   $12 parent_caution_id, $13 registered_at
    assert args.args[1] == _CAUTION_ID
    assert args.args[2] == "Asset"
    assert args.args[3] == _ASSET_ID
    assert args.args[4] == "Wear"
    assert args.args[5] == "Caution"
    assert args.args[6] == "hexapod stalls below 0.5 mm/s"
    assert args.args[7] == "run at 0.6 mm/s"
    assert args.args[8] == _AUTHOR_ID
    assert args.args[9] == ["alpha", "mu", "zeta"]
    assert args.args[10] is None  # expires_at
    assert args.args[11] is False  # propagate_to_children
    assert args.args[12] is None  # parent_caution_id (top-level register)
    assert args.args[13] == _NOW  # registered_at


@pytest.mark.unit
async def test_caution_registered_with_procedure_target_and_expires_at() -> None:
    proj = CautionSummaryProjection()
    conn = _conn_with_savepoint()
    expires = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    event = _stored(
        "CautionRegistered",
        _registered_payload(
            target={"kind": "Procedure", "id": str(_PROCEDURE_ID)},
            category="ProcedureGotcha",
            severity="Warning",
            expires_at=expires.isoformat(),
            propagate_to_children=True,
        ),
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] == "Procedure"
    assert args.args[3] == _PROCEDURE_ID
    assert args.args[4] == "ProcedureGotcha"
    assert args.args[5] == "Warning"
    assert args.args[10] == expires  # expires_at parsed
    assert args.args[11] is True  # propagate_to_children


@pytest.mark.unit
async def test_caution_registered_supersession_child_carries_parent_caution_id() -> None:
    """Supersession child genesis has parent_caution_id set to the parent's UUID."""
    proj = CautionSummaryProjection()
    conn = _conn_with_savepoint()
    event = _stored(
        "CautionRegistered",
        _registered_payload(parent_caution_id=str(_PARENT_CAUTION_ID)),
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[12] == _PARENT_CAUTION_ID


@pytest.mark.unit
async def test_caution_superseded_updates_status_and_links_child() -> None:
    proj = CautionSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CautionSuperseded",
        {
            "caution_id": str(_CAUTION_ID),
            "superseded_by_caution_id": str(_BY_CAUTION_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_caution_summary" in sql
    assert "status = 'Superseded'" in sql
    assert "superseded_by_caution_id = $2" in sql
    assert args.args[1] == _CAUTION_ID
    assert args.args[2] == _BY_CAUTION_ID
    assert args.args[3] == _NOW  # last_status_changed_at


@pytest.mark.unit
async def test_caution_retired_updates_status_and_reason() -> None:
    proj = CautionSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CautionRetired",
        {
            "caution_id": str(_CAUTION_ID),
            "reason": "Resolved",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_caution_summary" in sql
    assert "status = 'Retired'" in sql
    assert "retired_reason = $2" in sql
    assert args.args[1] == _CAUTION_ID
    assert args.args[2] == "Resolved"
    assert args.args[3] == _NOW  # last_status_changed_at


@pytest.mark.unit
async def test_projection_ignores_unsubscribed_event_type() -> None:
    """Foreign event types passed to apply() are no-ops (the worker should never
    deliver them, but defensive guard ensures we don't crash on contamination)."""
    proj = CautionSummaryProjection()
    conn = AsyncMock()
    await proj.apply(_stored("ImaginaryEvent", {}), conn)
    conn.execute.assert_not_awaited()
