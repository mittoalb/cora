"""Unit tests for the Dataset event union: payload round-trip + discriminator."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "DatasetRegistered"


@pytest.mark.unit
def test_to_payload_serializes_all_fields_with_nulls_and_empties() -> None:
    dataset_id = uuid4()
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload == {
        "dataset_id": str(dataset_id),
        "name": "D",
        "uri": "s3://b/k",
        "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
        "byte_size": 0,
        "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        "producing_run_id": None,
        "subject_id": None,
        "derived_from": [],
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_sorts_set_semantic_fields_deterministically() -> None:
    """Two registrations of the same logical Dataset produce byte-
    identical jsonb. Set-semantic fields (`derived_from`, `encoding.
    conforms_to`) sort canonically in the wire payload."""
    derived_a = uuid4()
    derived_b = uuid4()
    derived_c = uuid4()
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=1,
        media_type="application/x-hdf5",
        conforms_to=frozenset({"https://b.example/", "https://a.example/"}),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset({derived_a, derived_b, derived_c}),
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["encoding"]["conforms_to"] == ["https://a.example/", "https://b.example/"]
    assert payload["derived_from"] == sorted([str(derived_a), str(derived_b), str(derived_c)])


@pytest.mark.unit
def test_to_payload_serializes_optional_refs_when_set() -> None:
    run_id = uuid4()
    subject_id = uuid4()
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=run_id,
        subject_id=subject_id,
        derived_from=frozenset(),
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["producing_run_id"] == str(run_id)
    assert payload["subject_id"] == str(subject_id)


@pytest.mark.unit
def test_round_trip_through_stored_envelope() -> None:
    """to_payload + from_stored is a no-op on the in-memory event."""
    dataset_id = uuid4()
    run_id = uuid4()
    subject_id = uuid4()
    derived_id = uuid4()
    original = DatasetRegistered(
        dataset_id=dataset_id,
        name="32-ID Recon",
        uri="s3://aps-32id/runs/abc/recon.h5",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=1_073_741_824,
        media_type="application/x-hdf5",
        conforms_to=frozenset({"https://manual.nexusformat.org/"}),
        producing_run_id=run_id,
        subject_id=subject_id,
        derived_from=frozenset({derived_id}),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(original),
        payload=to_payload(original),
        occurred_at=original.occurred_at,
        event_id=uuid4(),
        command_name="RegisterDataset",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    # Round trip via the StoredEvent shape.
    from cora.infrastructure.ports.event_store import StoredEvent

    stored = StoredEvent(
        position=1,
        event_id=new_event.event_id,
        stream_type="Dataset",
        stream_id=dataset_id,
        version=1,
        event_type=new_event.event_type,
        schema_version=new_event.schema_version,
        payload=new_event.payload,
        correlation_id=new_event.correlation_id,
        causation_id=new_event.causation_id,
        occurred_at=new_event.occurred_at,
        recorded_at=new_event.occurred_at,
        metadata=new_event.metadata,
    )
    rebuilt = from_stored(stored)
    assert rebuilt == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Stream contamination fails loud rather than silently."""
    from cora.infrastructure.ports.event_store import StoredEvent

    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Dataset",
        stream_id=uuid4(),
        version=1,
        event_type="DatasetTeleported",
        schema_version=1,
        payload={},
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        metadata={},
    )
    with pytest.raises(ValueError, match="DatasetTeleported"):
        from_stored(stored)
