"""Unit tests for MethodSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 3
subscribed Method events. Postgres-side behavior is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.projections import MethodSummaryProjection

_METHOD_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Method",
        stream_id=_METHOD_ID,
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
    proj = MethodSummaryProjection()
    assert proj.name == "proj_recipe_method_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "MethodDefined",
            "MethodVersioned",
            "MethodDeprecated",
            "MethodParametersSchemaUpdated",
        }
    )


@pytest.mark.unit
async def test_projection_does_not_subscribe_to_other_aggregate_events() -> None:
    """Practice / Plan events belong in their own projections."""
    proj = MethodSummaryProjection()
    assert "PracticeDefined" not in proj.subscribed_event_types
    assert "PlanDefined" not in proj.subscribed_event_types


@pytest.mark.unit
async def test_method_defined_inserts_with_defined_status_and_null_version() -> None:
    proj = MethodSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "MethodDefined",
        {
            "method_id": str(_METHOD_ID),
            "name": "Continuous Rotation Tomography",
            "needed_family_ids": [str(uuid4())],
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_recipe_method_summary" in sql
    assert "ON CONFLICT (method_id) DO NOTHING" in sql
    assert "'Defined'" in sql
    assert "NULL" in sql
    assert args.args[1] == _METHOD_ID
    assert args.args[2] == "Continuous Rotation Tomography"
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_method_versioned_updates_status_and_version_tag() -> None:
    proj = MethodSummaryProjection()
    conn = AsyncMock()
    h = "a" * 64
    event = _stored(
        "MethodVersioned",
        {
            "method_id": str(_METHOD_ID),
            "version_tag": "v2.1.0",
            "occurred_at": _NOW.isoformat(),
            "content_hash": h,
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_method_summary" in sql
    assert "SET status = 'Versioned'" in sql
    assert "version_tag = $2" in sql
    assert "versioned_at = $3" in sql
    assert "content_hash = $4" in sql
    assert args.args[1] == _METHOD_ID
    assert args.args[2] == "v2.1.0"
    assert args.args[3] == _NOW
    assert args.args[4] == h


@pytest.mark.unit
async def test_method_versioned_pre_rollout_payload_writes_null_content_hash() -> None:
    """Legacy MethodVersioned events have no `content_hash` field; the
    projection MUST write NULL (not "" or "None") so equivalence
    queries can distinguish unattested rows from real hashes."""
    proj = MethodSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "MethodVersioned",
        {
            "method_id": str(_METHOD_ID),
            "version_tag": "v1",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] is None


@pytest.mark.unit
async def test_method_deprecated_updates_status_and_preserves_version_tag() -> None:
    proj = MethodSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "MethodDeprecated",
        {"method_id": str(_METHOD_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_method_summary" in sql
    assert "SET status = 'Deprecated'" in sql
    assert "version_tag" not in sql
    assert "deprecated_at = $2" in sql
    assert args.args[1] == _METHOD_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    proj = MethodSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_method_parameters_schema_updated_with_non_null_sets_present_true() -> None:
    """Schema-update event with non-null payload flips
    parameters_schema_present TRUE."""
    proj = MethodSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "MethodParametersSchemaUpdated",
        {
            "method_id": str(_METHOD_ID),
            "parameters_schema": {"$schema": "x", "type": "object"},
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_recipe_method_summary" in sql
    assert "parameters_schema_present" in sql
    assert args.args[1] == _METHOD_ID
    assert args.args[2] is True


@pytest.mark.unit
async def test_method_parameters_schema_updated_with_null_sets_present_false() -> None:
    """Clearing the schema flips parameters_schema_present back to FALSE."""
    proj = MethodSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "MethodParametersSchemaUpdated",
        {
            "method_id": str(_METHOD_ID),
            "parameters_schema": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] is False


@pytest.mark.unit
async def test_practice_defined_is_silently_dropped() -> None:
    """Cross-aggregate-event guard: PracticeDefined isn't in
    subscribed_event_types, but if the SQL filter ever lets one
    through, the bare match drops it without error."""
    proj = MethodSummaryProjection()
    conn = AsyncMock()
    event = _stored("PracticeDefined", {"practice_id": str(uuid4())})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


# ---------- gate-review test fill-ins (Path C) ----------


@pytest.mark.unit
async def test_method_versioned_replayed_overwrites_versioned_at() -> None:
    """Path C: re-version replaces `versioned_at` wholesale (state-
    always-holds-latest convention mirrored in projection). Two
    `MethodVersioned` events in sequence both execute UPDATE; SQL
    semantics ensure the second wins."""
    proj = MethodSummaryProjection()
    conn = AsyncMock()
    later = datetime(2026, 6, 1, 9, 30, 0, tzinfo=UTC)

    first = _stored(
        "MethodVersioned",
        {
            "method_id": str(_METHOD_ID),
            "version_tag": "v1.0.0",
            "occurred_at": _NOW.isoformat(),
        },
    )
    second = _stored(
        "MethodVersioned",
        {
            "method_id": str(_METHOD_ID),
            "version_tag": "v2.0.0",
            "occurred_at": later.isoformat(),
        },
    )

    await proj.apply(first, conn)
    await proj.apply(second, conn)

    assert conn.execute.await_count == 2
    second_args = conn.execute.await_args_list[1].args
    assert second_args[2] == "v2.0.0"
    assert second_args[3] == later


@pytest.mark.unit
async def test_method_lifecycle_timestamps_is_immutable_dataclass() -> None:
    """`MethodLifecycleTimestamps` is the projection-sourced VO read by
    the route layer (Path C). Frozen so callers can't mutate it under
    cached references; field shape pinned so future widening shows up
    as a deliberate change."""
    import dataclasses

    from cora.recipe.aggregates.method import MethodLifecycleTimestamps

    assert dataclasses.is_dataclass(MethodLifecycleTimestamps)
    field_names = {f.name for f in dataclasses.fields(MethodLifecycleTimestamps)}
    assert field_names == {"created_at", "versioned_at", "deprecated_at"}

    instance = MethodLifecycleTimestamps(
        created_at=_NOW,
        versioned_at=None,
        deprecated_at=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.versioned_at = _NOW  # type: ignore[misc]
