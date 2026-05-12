"""Unit tests for the `register_dataset` slice's pure decider.

Genesis-style decider: state must be None (otherwise
DatasetAlreadyExistsError); reason VOs validate the input;
cross-aggregate context refs validated against the command's
optional refs (existence-only per Q2 lock B).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Dataset,
    DatasetAlreadyExistsError,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetUri,
    DerivedFromDatasetsNotFoundError,
    InvalidDatasetByteSizeError,
    InvalidDatasetChecksumError,
    InvalidDatasetEncodingError,
    InvalidDatasetNameError,
    InvalidDatasetUriError,
    InvalidDerivedFromError,
    LinkedSubjectNotFoundError,
    ProducingRunNotFoundError,
)
from cora.data.features import register_dataset
from cora.data.features.register_dataset import (
    DatasetRegistrationContext,
    RegisterDataset,
)
from cora.run.aggregates.run import Run, RunName, RunStatus
from cora.subject.aggregates.subject import Subject, SubjectName

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _good_command(**overrides: object) -> RegisterDataset:
    base: dict[str, object] = {
        "name": "32-ID FlyScan recon",
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum_algorithm": "sha256",
        "checksum_value": _GOOD_SHA256,
        "byte_size": 1024,
        "media_type": "application/x-hdf5",
        "conforms_to": frozenset[str](),
        "producing_run_id": None,
        "subject_id": None,
        "derived_from": frozenset[UUID](),
    }
    base.update(overrides)
    return RegisterDataset(**base)  # type: ignore[arg-type]


def _existing_dataset() -> Dataset:
    return Dataset(
        id=uuid4(),
        name=DatasetName("seed"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
    )


def _fake_run() -> Run:
    return Run(
        id=uuid4(),
        name=RunName("seed-run"),
        plan_id=uuid4(),
        subject_id=uuid4(),
        status=RunStatus.RUNNING,
    )


def _fake_subject() -> Subject:
    return Subject(id=uuid4(), name=SubjectName("seed-subject"))


# ---------- Happy path ----------


@pytest.mark.unit
def test_decide_emits_dataset_registered_with_minimum_fields() -> None:
    new_id = uuid4()
    cmd = _good_command()
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert event.dataset_id == new_id
    assert event.name == "32-ID FlyScan recon"
    assert event.uri == "s3://aps-32id/runs/abc/recon.h5"
    assert event.checksum.algorithm == "sha256"
    assert event.checksum.value == _GOOD_SHA256
    assert event.byte_size == 1024
    assert event.encoding.media_type == "application/x-hdf5"
    assert event.encoding.conforms_to == frozenset()
    assert event.producing_run_id is None
    assert event.subject_id is None
    assert event.derived_from == frozenset()
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    cmd = _good_command(name="  trimmed  ")
    events = register_dataset.decide(
        state=None, command=cmd, context=DatasetRegistrationContext(), now=_NOW, new_id=uuid4()
    )
    assert events[0].name == "trimmed"


@pytest.mark.unit
def test_decide_trims_uri_via_value_object() -> None:
    cmd = _good_command(uri="  s3://b/k  ")
    events = register_dataset.decide(
        state=None, command=cmd, context=DatasetRegistrationContext(), now=_NOW, new_id=uuid4()
    )
    assert events[0].uri == "s3://b/k"


@pytest.mark.unit
def test_decide_accepts_zero_byte_size() -> None:
    cmd = _good_command(byte_size=0)
    events = register_dataset.decide(
        state=None, command=cmd, context=DatasetRegistrationContext(), now=_NOW, new_id=uuid4()
    )
    assert events[0].byte_size == 0


@pytest.mark.unit
def test_decide_accepts_encoding_conforms_to_set() -> None:
    cmd = _good_command(conforms_to=frozenset({"https://manual.nexusformat.org/"}))
    events = register_dataset.decide(
        state=None, command=cmd, context=DatasetRegistrationContext(), now=_NOW, new_id=uuid4()
    )
    assert events[0].encoding.conforms_to == frozenset({"https://manual.nexusformat.org/"})


# ---------- Field validation ----------


@pytest.mark.unit
def test_decide_raises_invalid_name_for_whitespace_only() -> None:
    cmd = _good_command(name="   ")
    with pytest.raises(InvalidDatasetNameError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_uri_for_missing_scheme() -> None:
    cmd = _good_command(uri="just-a-path")
    with pytest.raises(InvalidDatasetUriError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_checksum_for_md5() -> None:
    cmd = _good_command(checksum_algorithm="md5", checksum_value="d" * 32)
    with pytest.raises(InvalidDatasetChecksumError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_byte_size_for_negative() -> None:
    cmd = _good_command(byte_size=-1)
    with pytest.raises(InvalidDatasetByteSizeError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_encoding_for_empty_media_type() -> None:
    cmd = _good_command(media_type="")
    with pytest.raises(InvalidDatasetEncodingError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_derived_from_for_too_many_entries() -> None:
    cmd = _good_command(derived_from=frozenset(uuid4() for _ in range(65)))
    with pytest.raises(InvalidDerivedFromError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- Cross-aggregate context ----------


@pytest.mark.unit
def test_decide_passes_when_producing_run_set_and_loaded() -> None:
    run = _fake_run()
    cmd = _good_command(producing_run_id=run.id)
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(producing_run=run),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].producing_run_id == run.id


@pytest.mark.unit
def test_decide_raises_when_producing_run_set_but_context_missing() -> None:
    """Defensive: if the handler skipped its load (or the load returned
    None), the decider raises rather than silently producing a dangling
    reference."""
    run_id = uuid4()
    cmd = _good_command(producing_run_id=run_id)
    with pytest.raises(ProducingRunNotFoundError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(producing_run=None),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_when_subject_set_but_context_missing() -> None:
    subject_id = uuid4()
    cmd = _good_command(subject_id=subject_id)
    with pytest.raises(LinkedSubjectNotFoundError):
        register_dataset.decide(
            state=None,
            command=cmd,
            context=DatasetRegistrationContext(subject=None),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_when_derived_from_missing_in_context() -> None:
    derived_a = uuid4()
    derived_b = uuid4()
    cmd = _good_command(derived_from=frozenset({derived_a, derived_b}))
    existing = _existing_dataset()
    # Context only has one of them.
    ctx = DatasetRegistrationContext(derived_from={derived_a: existing})
    with pytest.raises(DerivedFromDatasetsNotFoundError) as exc_info:
        register_dataset.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.missing_ids == [derived_b]


@pytest.mark.unit
def test_decide_passes_with_full_cross_agg_context() -> None:
    run = _fake_run()
    subject = _fake_subject()
    derived = _existing_dataset()
    cmd = _good_command(
        producing_run_id=run.id,
        subject_id=subject.id,
        derived_from=frozenset({derived.id}),
    )
    events = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(
            producing_run=run,
            subject=subject,
            derived_from={derived.id: derived},
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].producing_run_id == run.id
    assert events[0].subject_id == subject.id
    assert events[0].derived_from == frozenset({derived.id})


# ---------- Strict-not-idempotent ----------


@pytest.mark.unit
def test_decide_raises_already_exists_when_state_not_none() -> None:
    existing = _existing_dataset()
    with pytest.raises(DatasetAlreadyExistsError) as exc_info:
        register_dataset.decide(
            state=existing,
            command=_good_command(),
            context=DatasetRegistrationContext(),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.dataset_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    cmd = _good_command()
    first = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=new_id,
    )
    second = register_dataset.decide(
        state=None,
        command=cmd,
        context=DatasetRegistrationContext(),
        now=_NOW,
        new_id=new_id,
    )
    assert first == second
