"""Unit tests for PlanSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 3
subscribed Plan events. Postgres-side behavior is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.projections import PlanSummaryProjection

_PLAN_ID = uuid4()
_PRACTICE_ID = uuid4()
_METHOD_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Plan",
        stream_id=_PLAN_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = PlanSummaryProjection()
    assert proj.name == "proj_recipe_plan_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "PlanDefined",
            "PlanVersioned",
            "PlanDeprecated",
            "PlanDefaultParametersUpdated",
        }
    )


@pytest.mark.unit
async def test_plan_defined_inserts_with_practice_id_and_method_id() -> None:
    """Plan carries practice_id + method_id in genesis payload; both
    must land in the projection. asset_ids and snapshots are
    intentionally NOT projected (deferred to a future join projection)."""
    proj = PlanSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "PlanDefined",
        {
            "plan_id": str(_PLAN_ID),
            "name": "TomographyOnUnit-32-ID",
            "practice_id": str(_PRACTICE_ID),
            "asset_ids": [str(uuid4())],
            "method_id": str(_METHOD_ID),
            "method_needed_families_snapshot": [str(uuid4())],
            "asset_families_snapshot": {},
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_recipe_plan_summary" in sql
    assert "ON CONFLICT (plan_id) DO NOTHING" in sql
    assert "'Defined'" in sql
    assert args.args[1] == _PLAN_ID
    assert args.args[2] == "TomographyOnUnit-32-ID"
    assert args.args[3] == _PRACTICE_ID
    assert args.args[4] == _METHOD_ID
    assert args.args[5] == _NOW


@pytest.mark.unit
async def test_plan_versioned_updates_status_and_version_tag() -> None:
    proj = PlanSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "PlanVersioned",
        {
            "plan_id": str(_PLAN_ID),
            "version_tag": "v3",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_plan_summary" in sql
    assert "SET status = 'Versioned'" in sql
    assert args.args[1] == _PLAN_ID
    assert args.args[2] == "v3"


@pytest.mark.unit
async def test_plan_deprecated_only_updates_status() -> None:
    proj = PlanSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "PlanDeprecated",
        {"plan_id": str(_PLAN_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_plan_summary" in sql
    assert "SET status = 'Deprecated'" in sql
    assert "practice_id" not in sql
    assert "method_id" not in sql
    assert "version_tag" not in sql


@pytest.mark.unit
async def test_plan_default_parameters_updated_with_non_empty_sets_present_true() -> None:
    """Phase 6g-b: defaults-update event with non-empty payload flips
    default_parameters_present TRUE."""
    proj = PlanSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "PlanDefaultParametersUpdated",
        {
            "plan_id": str(_PLAN_ID),
            "default_parameters": {"energy": 12.0},
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_plan_summary" in sql
    assert "default_parameters_present" in sql
    assert args.args[1] == _PLAN_ID
    assert args.args[2] is True


@pytest.mark.unit
async def test_plan_default_parameters_updated_with_empty_sets_present_false() -> None:
    """Phase 6g-b: clearing all keys (empty post-merge dict) flips
    default_parameters_present back to FALSE."""
    proj = PlanSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "PlanDefaultParametersUpdated",
        {
            "plan_id": str(_PLAN_ID),
            "default_parameters": {},
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] is False


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    proj = PlanSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
