"""Unit tests for CampaignSummaryProjection.

Pins per-event-type apply() dispatch for the 6 subscribed Campaign
events. Postgres-side behavior (CHECK constraints, GIN index round-
trips, drain, started_at preservation) is in the integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from cora.campaign.projections import CampaignSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent


def _conn_with_savepoint() -> AsyncMock:
    """AsyncMock conn whose `transaction()` returns an async context manager.

    The projection's `CampaignRegistered` arm wraps its INSERT in
    `async with conn.transaction(): ...` so any future cross-stream
    uniqueness violation rolls back only the inner SAVEPOINT (not the
    worker's outer batch txn). Mirrors the supply / caution projection
    test idiom.
    """
    conn = AsyncMock()
    transaction_cm = AsyncMock()
    transaction_cm.__aenter__.return_value = None
    transaction_cm.__aexit__.return_value = None
    conn.transaction = MagicMock(return_value=transaction_cm)
    return conn


_CAMPAIGN_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_PRINCIPAL_ID = uuid4()
_LEAD_ACTOR_ID = uuid4()
_SUBJECT_ID = uuid4()
_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Campaign",
        stream_id=_CAMPAIGN_ID,
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
        "campaign_id": str(_CAMPAIGN_ID),
        "name": "operando battery, week of 2026-05-17",
        "intent": "Operando",
        "lead_actor_id": str(_LEAD_ACTOR_ID),
        "subject_id": None,
        "description": None,
        "tags": [],
        "external_refs": [],
        "external_id": None,
        "occurred_at": _NOW.isoformat(),
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = CampaignSummaryProjection()
    assert proj.name == "proj_recipe_campaign_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "CampaignRegistered",
            "CampaignStarted",
            "CampaignHeld",
            "CampaignResumed",
            "CampaignClosed",
            "CampaignAbandoned",
            # Phase 6i-c membership arms.
            "CampaignRunAdded",
            "CampaignRunRemoved",
        }
    )


@pytest.mark.unit
def test_projection_does_not_subscribe_to_unrelated_events() -> None:
    """Foreign event types belong to other projections."""
    proj = CampaignSummaryProjection()
    for foreign in (
        "CautionRegistered",
        "SupplyRegistered",
        "ClearanceRegistered",
        "RunStarted",
    ):
        assert foreign not in proj.subscribed_event_types


@pytest.mark.unit
async def test_campaign_registered_inserts_with_planned_status_and_null_audit() -> None:
    proj = CampaignSummaryProjection()
    conn = _conn_with_savepoint()
    event = _stored("CampaignRegistered", _registered_payload())

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    conn.transaction.assert_called_once()  # SAVEPOINT engaged for the INSERT
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_recipe_campaign_summary" in sql
    assert "ON CONFLICT (campaign_id) DO NOTHING" in sql
    assert "'Planned'" in sql  # status literal
    # Bound parameters (positional):
    #   $1 campaign_id, $2 name, $3 intent, $4 lead_actor_id,
    #   $5 subject_id, $6 description, $7 tags, $8 external_id,
    #   $9 registered_at
    assert args.args[1] == _CAMPAIGN_ID
    assert args.args[2] == "operando battery, week of 2026-05-17"
    assert args.args[3] == "Operando"
    assert args.args[4] == _LEAD_ACTOR_ID
    assert args.args[5] is None  # subject_id
    assert args.args[6] is None  # description
    assert args.args[7] == []  # tags
    assert args.args[8] is None  # external_id
    assert args.args[9] == _NOW  # registered_at


@pytest.mark.unit
async def test_campaign_registered_with_subject_description_tags_and_external_id() -> None:
    proj = CampaignSummaryProjection()
    conn = _conn_with_savepoint()
    event = _stored(
        "CampaignRegistered",
        _registered_payload(
            subject_id=str(_SUBJECT_ID),
            description="In-situ heating of NMC811 cathode at 200C",
            tags=["alpha", "operando", "thermal"],
            external_id="DOI:10.example/proj-2026-001",
        ),
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[5] == _SUBJECT_ID
    assert args.args[6] == "In-situ heating of NMC811 cathode at 200C"
    assert args.args[7] == ["alpha", "operando", "thermal"]
    assert args.args[8] == "DOI:10.example/proj-2026-001"


@pytest.mark.unit
async def test_campaign_started_sets_status_active_and_started_at() -> None:
    """CampaignStarted is the FIRST start (Planned -> Active); started_at is set."""
    proj = CampaignSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CampaignStarted",
        {
            "campaign_id": str(_CAMPAIGN_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_campaign_summary" in sql
    assert "status = 'Active'" in sql
    assert "started_at = $2" in sql
    assert "last_status_changed_at = $2" in sql
    assert args.args[1] == _CAMPAIGN_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_campaign_held_sets_status_held_with_reason_and_audit_ts() -> None:
    proj = CampaignSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CampaignHeld",
        {
            "campaign_id": str(_CAMPAIGN_ID),
            "reason": "beam dump unscheduled outage",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_campaign_summary" in sql
    assert "status = 'Held'" in sql
    assert "last_status_reason = $2" in sql
    assert "last_status_changed_at = $3" in sql
    assert args.args[1] == _CAMPAIGN_ID
    assert args.args[2] == "beam dump unscheduled outage"
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_campaign_resumed_sets_status_active_without_touching_reason() -> None:
    """CampaignResumed preserves last_status_reason (audit value per design memo)."""
    proj = CampaignSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CampaignResumed",
        {
            "campaign_id": str(_CAMPAIGN_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_campaign_summary" in sql
    assert "status = 'Active'" in sql
    assert "last_status_changed_at = $2" in sql
    # CRITICAL: the RESUME SQL must NOT mention `last_status_reason` -- it preserves
    # the prior value (set by the prior Held event) for audit-breadcrumb readability.
    assert "last_status_reason" not in sql
    # And the resume SQL also must NOT touch started_at (set on first Started only).
    assert "started_at" not in sql
    assert args.args[1] == _CAMPAIGN_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_campaign_closed_sets_status_closed_and_audit_ts() -> None:
    proj = CampaignSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CampaignClosed",
        {
            "campaign_id": str(_CAMPAIGN_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_campaign_summary" in sql
    assert "status = 'Closed'" in sql
    assert "last_status_changed_at = $2" in sql
    # Close is a NORMAL terminal; no reason field. The SQL must not mention reason.
    assert "last_status_reason" not in sql
    assert args.args[1] == _CAMPAIGN_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_campaign_abandoned_sets_status_abandoned_with_reason() -> None:
    proj = CampaignSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CampaignAbandoned",
        {
            "campaign_id": str(_CAMPAIGN_ID),
            "reason": "sample damaged beyond recovery",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_campaign_summary" in sql
    assert "status = 'Abandoned'" in sql
    assert "last_status_reason = $2" in sql
    assert "last_status_changed_at = $3" in sql
    assert args.args[1] == _CAMPAIGN_ID
    assert args.args[2] == "sample damaged beyond recovery"
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_projection_ignores_unsubscribed_event_type() -> None:
    """Foreign event types passed to apply() are no-ops (defensive guard)."""
    proj = CampaignSummaryProjection()
    conn = AsyncMock()
    await proj.apply(_stored("ImaginaryEvent", {}), conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_campaign_run_added_increments_run_count() -> None:
    """Phase 6i-c: CampaignRunAdded bumps run_count by one."""
    proj = CampaignSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CampaignRunAdded",
        {
            "campaign_id": str(_CAMPAIGN_ID),
            "run_id": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_campaign_summary" in sql
    assert "run_count = run_count + 1" in sql
    assert args.args[1] == _CAMPAIGN_ID


@pytest.mark.unit
async def test_campaign_run_removed_decrements_run_count() -> None:
    """Phase 6i-c: CampaignRunRemoved drops run_count by one."""
    proj = CampaignSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "CampaignRunRemoved",
        {
            "campaign_id": str(_CAMPAIGN_ID),
            "run_id": str(uuid4()),
            "reason": "operator removed",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_campaign_summary" in sql
    assert "run_count = run_count - 1" in sql
    assert args.args[1] == _CAMPAIGN_ID
