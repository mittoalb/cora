"""Unit tests for AttestationSummaryProjection."""

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from cora.data.projections import AttestationSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_ATTESTATION_ID = uuid4()
_DATASET_ID = uuid4()
_DISTRIBUTION_ID = uuid4()
_SUPPLY_ID = uuid4()
_ATTESTED_BY = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 10, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Attestation",
        stream_id=_ATTESTATION_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _recorded_payload(
    *,
    distribution_id: UUID | None = _DISTRIBUTION_ID,
    outcome: str = "Match",
    computed_value: str | None = "a" * 64,
) -> dict[str, Any]:
    return {
        "attestation_id": str(_ATTESTATION_ID),
        "dataset_id": str(_DATASET_ID),
        "distribution_id": str(distribution_id) if distribution_id is not None else None,
        "kind": "ChecksumVerified",
        "outcome": outcome,
        "evidence": {
            "algorithm": "sha256",
            "value": computed_value,
            "verifier_supply_id": str(_SUPPLY_ID),
            "verifier_kind": "HttpRangeChecksum",
        },
        "occurred_at": _NOW.isoformat(),
        "attested_by": str(_ATTESTED_BY),
    }


@pytest.mark.unit
def test_projection_metadata_subscribes_to_attestation_recorded_only() -> None:
    proj = AttestationSummaryProjection()
    assert proj.name == "proj_data_attestation_summary"
    assert proj.subscribed_event_types == frozenset({"AttestationRecorded"})


@pytest.mark.unit
async def test_attestation_recorded_inserts_all_fields() -> None:
    proj = AttestationSummaryProjection()
    conn = AsyncMock()
    event = _stored("AttestationRecorded", _recorded_payload())

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_data_attestation_summary" in sql
    assert "ON CONFLICT (attestation_id) DO NOTHING" in sql
    assert args.args[1] == _ATTESTATION_ID
    assert args.args[2] == _DATASET_ID
    assert args.args[3] == _DISTRIBUTION_ID
    assert args.args[4] == "ChecksumVerified"
    assert args.args[5] == "Match"
    # evidence is JSONB-cast string of the wire dict.
    assert json.loads(args.args[6])["algorithm"] == "sha256"
    assert args.args[7] == _NOW
    assert args.args[8] == _ATTESTED_BY


@pytest.mark.unit
async def test_attestation_recorded_inserts_null_distribution_for_conforms_to_arm() -> None:
    proj = AttestationSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AttestationRecorded",
        _recorded_payload(distribution_id=None),
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[3] is None


@pytest.mark.unit
async def test_attestation_recorded_handles_unreachable_with_null_value() -> None:
    proj = AttestationSummaryProjection()
    conn = AsyncMock()
    payload = _recorded_payload(outcome="Unreachable", computed_value=None)
    payload["evidence"]["error_detail"] = "HEAD 503"
    event = _stored("AttestationRecorded", payload)
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[5] == "Unreachable"
    assert json.loads(args.args[6])["value"] is None
    assert json.loads(args.args[6])["error_detail"] == "HEAD 503"


@pytest.mark.unit
async def test_unknown_event_type_falls_through() -> None:
    proj = AttestationSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_attestation_recorded_passes_uuid_typed_ids() -> None:
    proj = AttestationSummaryProjection()
    conn = AsyncMock()
    event = _stored("AttestationRecorded", _recorded_payload())
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert isinstance(args.args[1], UUID)
    assert isinstance(args.args[2], UUID)
    assert isinstance(args.args[3], UUID)
    assert isinstance(args.args[8], UUID)
