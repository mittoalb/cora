"""Unit tests for the ``record_attestation`` application handler.

Mirror of ``register_distribution`` handler test shape: VOs validated,
authz called, idempotency-not-tested (wire decorator's job),
cross-aggregate context loaded from a real in-memory event store.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import DataHandlers, UnauthorizedError, wire_data
from cora.data.aggregates.attestation import (
    AttestationDistributionNotFoundError,
    AttestationKindNotYetSupportedError,
)
from cora.data.aggregates.dataset import DatasetNotFoundError
from cora.data.aggregates.dataset.events import (
    DatasetRegistered,
)
from cora.data.aggregates.dataset.events import (
    event_type_name as dataset_event_type_name,
)
from cora.data.aggregates.dataset.events import (
    to_payload as dataset_to_payload,
)
from cora.data.aggregates.distribution.events import (
    DistributionRegistered,
)
from cora.data.aggregates.distribution.events import (
    event_type_name as distribution_event_type_name,
)
from cora.data.aggregates.distribution.events import (
    to_payload as distribution_to_payload,
)
from cora.data.features import record_attestation
from cora.data.features.record_attestation import RecordAttestation
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA = "a" * 64
_OTHER_SHA = "b" * 64
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_ATTESTATION_ID = UUID("01900000-0000-7000-8000-00000000a771")
_REG_EVENT_ID = UUID("01900000-0000-7000-8000-00000000a772")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DATASET_ID = UUID("01900000-0000-7000-8000-00000000da7a")
_DISTRIBUTION_ID = UUID("01900000-0000-7000-8000-0000000d1571")
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005519")


def _good_command(**overrides: object) -> RecordAttestation:
    base: dict[str, object] = {
        "dataset_id": _DATASET_ID,
        "distribution_id": _DISTRIBUTION_ID,
        "kind": "ChecksumVerified",
        "outcome": "Match",
        "evidence_expected_checksum": _GOOD_SHA,
        "evidence_computed_checksum": _GOOD_SHA,
        "evidence_algorithm": "sha256",
        "evidence_verifier_supply_id": _SUPPLY_ID,
        "evidence_verifier_kind": "HttpRangeChecksum",
        "evidence_error_detail": None,
    }
    base.update(overrides)
    return RecordAttestation(**base)  # type: ignore[arg-type]


async def _seed_dataset(
    store: InMemoryEventStore,
    dataset_id: UUID = _DATASET_ID,
    *,
    checksum_value: str = _GOOD_SHA,
    byte_size: int = 1024,
) -> None:
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="seed",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=checksum_value,
        byte_size=byte_size,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        registered_by=ActorId(_PRINCIPAL_ID),
    )
    new_event = to_new_event(
        event_type=dataset_event_type_name(event),
        payload=dataset_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterDataset",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Dataset", stream_id=dataset_id, expected_version=0, events=[new_event]
    )


async def _seed_distribution(
    store: InMemoryEventStore,
    distribution_id: UUID = _DISTRIBUTION_ID,
    *,
    dataset_id: UUID = _DATASET_ID,
    checksum_value: str = _GOOD_SHA,
) -> None:
    event = DistributionRegistered(
        distribution_id=distribution_id,
        dataset_id=dataset_id,
        supply_id=_SUPPLY_ID,
        uri="s3://b/k.h5",
        checksum_algorithm="sha256",
        checksum_value=checksum_value,
        byte_size=1024,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        access_protocol="S3",
        occurred_at=_NOW,
        registered_by=ActorId(_PRINCIPAL_ID),
    )
    new_event = to_new_event(
        event_type=distribution_event_type_name(event),
        payload=distribution_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterDistribution",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Distribution",
        stream_id=distribution_id,
        expected_version=0,
        events=[new_event],
    )


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_returns_new_attestation_id_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    attestation_id = await record_attestation.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert attestation_id == _ATTESTATION_ID


@pytest.mark.unit
async def test_handler_appends_attestation_recorded_event_with_canonical_payload() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await record_attestation.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Attestation", _ATTESTATION_ID)
    assert version == 1
    assert [e.event_type for e in events] == ["AttestationRecorded"]
    recorded = events[0]
    assert recorded.event_id == _REG_EVENT_ID
    assert recorded.metadata == {"command": "RecordAttestation"}
    payload = recorded.payload
    assert payload["attestation_id"] == str(_ATTESTATION_ID)
    assert payload["dataset_id"] == str(_DATASET_ID)
    assert payload["distribution_id"] == str(_DISTRIBUTION_ID)
    assert payload["kind"] == "ChecksumVerified"
    assert payload["outcome"] == "Match"
    assert payload["evidence"]["algorithm"] == "sha256"
    assert payload["evidence"]["value"] == _GOOD_SHA
    assert payload["evidence"]["verifier_supply_id"] == str(_SUPPLY_ID)
    assert payload["evidence"]["verifier_kind"] == "HttpRangeChecksum"
    assert payload["attested_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await record_attestation.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Attestation", _ATTESTATION_ID)
    assert events[0].causation_id == causation


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    await _seed_distribution(store)
    deps = build_deps(
        ids=[_ATTESTATION_ID, _REG_EVENT_ID],
        now=_NOW,
        event_store=store,
        deny=True,
    )
    with pytest.raises(UnauthorizedError):
        await record_attestation.bind(deps)(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, _ = await store.load("Attestation", _ATTESTATION_ID)
    assert events == []


# ---------- Handler-tier kind-not-yet-supported guard ----------


@pytest.mark.unit
async def test_handler_raises_kind_not_yet_supported_before_loading_dataset() -> None:
    store = InMemoryEventStore()
    # Intentionally do NOT seed the Dataset: the kind guard must fire
    # before the Dataset pre-load to avoid information leakage.
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(AttestationKindNotYetSupportedError):
        await record_attestation.bind(deps)(
            _good_command(kind="FormatValidated"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Cross-aggregate validation ----------


@pytest.mark.unit
async def test_handler_raises_dataset_not_found_when_dataset_missing() -> None:
    store = InMemoryEventStore()
    await _seed_distribution(store, dataset_id=_DATASET_ID)
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    missing = uuid4()
    with pytest.raises(DatasetNotFoundError):
        await record_attestation.bind(deps)(
            _good_command(dataset_id=missing),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_distribution_not_found_when_missing() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store)
    # NOTE: no seed_distribution call.
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(AttestationDistributionNotFoundError):
        await record_attestation.bind(deps)(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Wire bundle ----------


@pytest.mark.unit
def test_wire_data_includes_record_attestation() -> None:
    deps = build_deps(ids=[_ATTESTATION_ID, _REG_EVENT_ID], now=_NOW)
    handlers = wire_data(deps)
    assert isinstance(handlers, DataHandlers)
    assert callable(handlers.record_attestation)
