"""Unit tests for PracticeSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 3
subscribed Practice events. Postgres-side behavior is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.projections import PracticeSummaryProjection

_PRACTICE_ID = uuid4()
_METHOD_ID = uuid4()
_SITE_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Practice",
        stream_id=_PRACTICE_ID,
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
    proj = PracticeSummaryProjection()
    assert proj.name == "proj_recipe_practice_summary"
    assert proj.subscribed_event_types == frozenset(
        {"PracticeDefined", "PracticeVersioned", "PracticeDeprecated"}
    )


@pytest.mark.unit
async def test_practice_defined_inserts_with_method_id_and_site_id() -> None:
    """Practice carries cross-aggregate refs (method_id, site_id) in
    the genesis payload; both must land in the projection."""
    proj = PracticeSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "PracticeDefined",
        {
            "practice_id": str(_PRACTICE_ID),
            "name": "APS-2BM-CT-routine",
            "method_id": str(_METHOD_ID),
            "site_id": str(_SITE_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_recipe_practice_summary" in sql
    assert "ON CONFLICT (practice_id) DO NOTHING" in sql
    assert "'Defined'" in sql
    assert args.args[1] == _PRACTICE_ID
    assert args.args[2] == "APS-2BM-CT-routine"
    assert args.args[3] == _METHOD_ID
    assert args.args[4] == _SITE_ID
    assert args.args[5] == _NOW


@pytest.mark.unit
async def test_practice_versioned_updates_status_and_version_tag() -> None:
    proj = PracticeSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "PracticeVersioned",
        {
            "practice_id": str(_PRACTICE_ID),
            "version_tag": "2026-Q3",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_practice_summary" in sql
    assert "SET status = 'Versioned'" in sql
    assert "versioned_at = $3" in sql
    assert args.args[1] == _PRACTICE_ID
    assert args.args[2] == "2026-Q3"
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_practice_deprecated_does_not_touch_method_or_site() -> None:
    """Pin: deprecation only flips status; method_id, site_id, and
    version_tag are intentionally left alone (audit trail of "what
    binding was last revised before deprecation" preserved)."""
    proj = PracticeSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "PracticeDeprecated",
        {"practice_id": str(_PRACTICE_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_practice_summary" in sql
    assert "SET status = 'Deprecated'" in sql
    assert "deprecated_at = $2" in sql
    assert "method_id" not in sql
    assert "site_id" not in sql
    assert "version_tag" not in sql
    assert args.args[1] == _PRACTICE_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    proj = PracticeSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
