"""Unit tests for DistributionSummaryProjection."""

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from asyncpg.exceptions import UniqueViolationError

from cora.data.projections import DistributionSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_DISTRIBUTION_ID = uuid4()
_DATASET_ID = uuid4()
_SUPPLY_ID = uuid4()
_REGISTERED_BY = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 9, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Distribution",
        stream_id=_DISTRIBUTION_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _registered_payload() -> dict[str, Any]:
    return {
        "distribution_id": str(_DISTRIBUTION_ID),
        "dataset_id": str(_DATASET_ID),
        "supply_id": str(_SUPPLY_ID),
        "uri": "s3://bucket/key.h5",
        "checksum": {"algorithm": "sha256", "value": "deadbeef" * 8},
        "byte_size": 1024,
        "encoding": {
            "media_type": "application/x-hdf5",
            "conforms_to": ["https://manual.nexusformat.org/"],
        },
        "access_protocol": "S3",
        "occurred_at": _NOW.isoformat(),
        "registered_by": str(_REGISTERED_BY),
    }


@pytest.mark.unit
def test_projection_metadata() -> None:
    """Today ships ONE subscribed event; the Attestation projection-
    writer extension adds AttestationRecorded later (frozenset will be
    revised then). Pin the current shape so the cross-memo merge
    ordering surfaces at the unit tier per L27."""
    proj = DistributionSummaryProjection()
    assert proj.name == "proj_data_distribution_summary"
    assert proj.subscribed_event_types == frozenset({"DistributionRegistered"})


@pytest.mark.unit
async def test_distribution_registered_inserts_all_fields() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    event = _stored("DistributionRegistered", _registered_payload())

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_data_distribution_summary" in sql
    assert "ON CONFLICT (distribution_id) DO NOTHING" in sql
    assert "'Registered'" in sql

    assert args.args[1] == _DISTRIBUTION_ID
    assert args.args[2] == _DATASET_ID
    assert args.args[3] == _SUPPLY_ID
    assert args.args[4] == "s3://bucket/key.h5"
    # checksum + encoding are JSONB; the writer pre-serializes dicts to
    # strings for asyncpg's $N::jsonb cast.
    assert json.loads(args.args[5]) == {"algorithm": "sha256", "value": "deadbeef" * 8}
    assert args.args[6] == 1024
    assert json.loads(args.args[7]) == {
        "media_type": "application/x-hdf5",
        "conforms_to": ["https://manual.nexusformat.org/"],
    }
    assert args.args[8] == "S3"
    assert args.args[9] == _NOW
    assert args.args[10] == _REGISTERED_BY


@pytest.mark.unit
async def test_distribution_registered_swallows_unique_violation() -> None:
    """Per L31 / Supply projection-writer precedent: the partial UNIQUE
    INDEX collision on (dataset_id, supply_id, uri) is caught, logged
    WARN, and the bookmark advances. The writer does NOT raise."""
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    conn.execute.side_effect = UniqueViolationError("simulated triple collision")
    event = _stored("DistributionRegistered", _registered_payload())

    # Must NOT raise; writer-side swallow allows bookmark to advance.
    await proj.apply(event, conn)

    conn.execute.assert_awaited()


@pytest.mark.unit
async def test_unknown_event_type_falls_through() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
def test_subscribed_event_types_carries_only_genesis() -> None:
    """Negative-shape pin so the Attestation Slice C extension is a
    visible additive diff against this assertion (per L27 merge-order
    coordination)."""
    proj = DistributionSummaryProjection()
    assert "AttestationRecorded" not in proj.subscribed_event_types
    assert "DistributionVerified" not in proj.subscribed_event_types
    assert "DistributionMarkedStale" not in proj.subscribed_event_types
    assert "DistributionDiscarded" not in proj.subscribed_event_types


# Pin the distribution_id type asyncpg sees so a string-vs-UUID drift
# regression fails at the unit tier instead of slipping to integration.
@pytest.mark.unit
async def test_distribution_registered_passes_uuid_typed_ids() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    event = _stored("DistributionRegistered", _registered_payload())

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert isinstance(args.args[1], UUID)
    assert isinstance(args.args[2], UUID)
    assert isinstance(args.args[3], UUID)
    assert isinstance(args.args[10], UUID)
