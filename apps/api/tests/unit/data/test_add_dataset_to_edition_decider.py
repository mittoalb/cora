"""Unit tests for the `add_dataset_to_edition` pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Dataset,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetStatus,
    DatasetUri,
)
from cora.data.aggregates.edition import (
    Creator,
    Edition,
    EditionCannotBindToDiscardedDatasetError,
    EditionDatasetAlreadyMemberError,
    EditionKind,
    EditionNotFoundError,
    EditionNotInRegisteredStateError,
    EditionStatus,
    EditionTitle,
)
from cora.data.features import add_dataset_to_edition
from cora.data.features.add_dataset_to_edition import (
    AddDatasetToEdition,
    AddDatasetToEditionContext,
)
from cora.shared.identity import ActorId

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_ADDED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000aa"))


def _dataset(
    dataset_id: UUID,
    *,
    status: DatasetStatus = DatasetStatus.REGISTERED,
) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        status=status,
    )


def _edition(
    edition_id: UUID,
    *,
    dataset_ids: frozenset[UUID],
    status: EditionStatus = EditionStatus.REGISTERED,
) -> Edition:
    return Edition(
        id=edition_id,
        kind=EditionKind.ROCRATE,
        title=EditionTitle("E"),
        dataset_ids=dataset_ids,
        creators=(Creator(actor_id=ActorId(uuid4())),),
        registered_at=_NOW,
        registered_by=_ADDED_BY,
        status=status,
    )


# ---------- Happy ----------


@pytest.mark.unit
def test_decide_emits_dataset_added() -> None:
    edition_id = uuid4()
    existing = uuid4()
    new = uuid4()
    state = _edition(edition_id, dataset_ids=frozenset({existing}))
    ctx = AddDatasetToEditionContext(dataset=_dataset(new))
    events = add_dataset_to_edition.decide(
        state=state,
        command=AddDatasetToEdition(edition_id=edition_id, dataset_id=new),
        context=ctx,
        now=_NOW,
        added_by=_ADDED_BY,
    )
    assert len(events) == 1
    event = events[0]
    assert event.edition_id == edition_id
    assert event.dataset_id == new
    assert event.occurred_at == _NOW
    assert event.added_by == _ADDED_BY


# ---------- Rejections ----------


@pytest.mark.unit
def test_decide_raises_when_state_is_none() -> None:
    edition_id = uuid4()
    new = uuid4()
    ctx = AddDatasetToEditionContext(dataset=_dataset(new))
    with pytest.raises(EditionNotFoundError) as exc:
        add_dataset_to_edition.decide(
            state=None,
            command=AddDatasetToEdition(edition_id=edition_id, dataset_id=new),
            context=ctx,
            now=_NOW,
            added_by=_ADDED_BY,
        )
    assert exc.value.edition_id == edition_id


@pytest.mark.unit
def test_decide_raises_when_edition_not_in_registered_state() -> None:
    edition_id = uuid4()
    existing = uuid4()
    new = uuid4()
    state = _edition(edition_id, dataset_ids=frozenset({existing}), status=EditionStatus.SEALED)
    ctx = AddDatasetToEditionContext(dataset=_dataset(new))
    with pytest.raises(EditionNotInRegisteredStateError) as exc:
        add_dataset_to_edition.decide(
            state=state,
            command=AddDatasetToEdition(edition_id=edition_id, dataset_id=new),
            context=ctx,
            now=_NOW,
            added_by=_ADDED_BY,
        )
    assert exc.value.current_status is EditionStatus.SEALED


@pytest.mark.unit
def test_decide_raises_when_dataset_is_discarded() -> None:
    edition_id = uuid4()
    existing = uuid4()
    new = uuid4()
    state = _edition(edition_id, dataset_ids=frozenset({existing}))
    ctx = AddDatasetToEditionContext(dataset=_dataset(new, status=DatasetStatus.DISCARDED))
    with pytest.raises(EditionCannotBindToDiscardedDatasetError) as exc:
        add_dataset_to_edition.decide(
            state=state,
            command=AddDatasetToEdition(edition_id=edition_id, dataset_id=new),
            context=ctx,
            now=_NOW,
            added_by=_ADDED_BY,
        )
    assert exc.value.dataset_id == new


@pytest.mark.unit
def test_decide_raises_when_dataset_already_member() -> None:
    edition_id = uuid4()
    existing = uuid4()
    state = _edition(edition_id, dataset_ids=frozenset({existing}))
    ctx = AddDatasetToEditionContext(dataset=_dataset(existing))
    with pytest.raises(EditionDatasetAlreadyMemberError) as exc:
        add_dataset_to_edition.decide(
            state=state,
            command=AddDatasetToEdition(edition_id=edition_id, dataset_id=existing),
            context=ctx,
            now=_NOW,
            added_by=_ADDED_BY,
        )
    assert exc.value.dataset_id == existing
