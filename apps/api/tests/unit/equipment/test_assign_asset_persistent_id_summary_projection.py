"""Unit tests for AssetSummaryProjection's AssetPersistentIdAssigned handling.

Pins the JSONB-shape contract for the persistent_id column written by
the projection when an AssetPersistentIdAssigned event lands. The
neighbor `test_asset_summary_projection.py` covers the projector's other
arms; this file isolates the slice-F arm so a regression in the
JSONB-build SQL or the (scheme, value) carry surfaces as a focused
failure. Integration-tier real-PG behavior (replay, codecs) lives in
`tests/integration/test_postgres_asset_summary_projection.py`.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections import AssetSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]

_ASSET_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Asset",
        stream_id=_ASSET_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _persistent_id_assigned(
    *, scheme: str = "DOI", value: str = "10.5281/zenodo.1234567"
) -> StoredEvent:
    return _stored(
        "AssetPersistentIdAssigned",
        {
            "asset_id": str(_ASSET_ID),
            "persistent_id_scheme": scheme,
            "persistent_id_value": value,
            "occurred_at": _NOW.isoformat(),
        },
    )


async def test_apply_assigned_writes_persistent_id_jsonb() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _persistent_id_assigned(scheme="DOI", value="10.5281/zenodo.1234567")

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_asset_summary" in sql
    assert "SET persistent_id" in sql
    assert "jsonb_build_object" in sql
    assert "WHERE asset_id = $1" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == "DOI"
    assert args.args[3] == "10.5281/zenodo.1234567"


async def test_jsonb_shape_is_scheme_value_object() -> None:
    """The JSONB column is built from `jsonb_build_object('scheme', ..., 'value', ...)`
    so the on-disk row is `{"scheme": <str>, "value": <str>}`. Pin the SQL
    keys so a future refactor that swaps to `'type'` / `'identifier'`
    (PIDINST wire vocabulary) breaks this test before it breaks the
    serializer."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _persistent_id_assigned(scheme="Handle", value="20.500.12613/12345")

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "'scheme'" in sql
    assert "'value'" in sql
    assert "$2::text" in sql
    assert "$3::text" in sql
    assert args.args[2] == "Handle"
    assert args.args[3] == "20.500.12613/12345"


async def test_apply_twice_with_same_event_is_idempotent_at_jsonb_column_level() -> None:
    """Calling apply() twice on the same AssetPersistentIdAssigned event
    issues the same UPDATE both times with identical bound parameters.
    The persistent_id JSONB column ends in the same `{"scheme", "value"}`
    shape after both invocations (the projection's UPDATE is an absolute
    overwrite, not an append). Defends against a regression where a
    second apply() would null-out, duplicate, or wrap the column."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _persistent_id_assigned(scheme="DOI", value="10.5281/zenodo.1234567")

    await proj.apply(event, conn)
    await proj.apply(event, conn)

    assert conn.execute.await_count == 2
    first, second = conn.execute.await_args_list
    assert first.args == second.args
    sql = first.args[0]
    assert "UPDATE proj_equipment_asset_summary" in sql
    assert "SET persistent_id" in sql
    assert first.args[1] == _ASSET_ID
    assert first.args[2] == "DOI"
    assert first.args[3] == "10.5281/zenodo.1234567"
