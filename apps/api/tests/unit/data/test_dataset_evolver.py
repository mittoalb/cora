"""Unit tests for the Dataset evolver.

7a ships one event arm (DatasetRegistered → REGISTERED). The
exhaustiveness guard (assert_never) makes this test set tiny but
locks the genesis arm's shape.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetChecksum,
    DatasetEncoding,
    DatasetRegistered,
    DatasetStatus,
    evolve,
    fold,
)

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_registered_creates_dataset_with_registered_status() -> None:
    dataset_id = uuid4()
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="D",
        uri="s3://b/k",
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=42,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
    )
    state = evolve(state=None, event=event)
    assert state.id == dataset_id
    assert state.name.value == "D"
    assert state.uri.value == "s3://b/k"
    assert state.checksum.algorithm == "sha256"
    assert state.checksum.value == _GOOD_SHA256
    assert state.byte_size == 42
    assert state.encoding.media_type == "application/x-hdf5"
    assert state.encoding.conforms_to == frozenset()
    assert state.producing_run_id is None
    assert state.subject_id is None
    assert state.derived_from == frozenset()
    assert state.status is DatasetStatus.REGISTERED


@pytest.mark.unit
def test_evolve_preserves_optional_refs() -> None:
    run_id = uuid4()
    subject_id = uuid4()
    derived = uuid4()
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://manual.nexusformat.org/"}),
        ),
        producing_run_id=run_id,
        subject_id=subject_id,
        derived_from=frozenset({derived}),
        occurred_at=_NOW,
    )
    state = evolve(state=None, event=event)
    assert state.producing_run_id == run_id
    assert state.subject_id == subject_id
    assert state.derived_from == frozenset({derived})
    assert state.encoding.conforms_to == frozenset({"https://manual.nexusformat.org/"})


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_register_event_returns_dataset() -> None:
    event = DatasetRegistered(
        dataset_id=uuid4(),
        name="D",
        uri="s3://b/k",
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
    )
    state = fold([event])
    assert state is not None
    assert state.status is DatasetStatus.REGISTERED
