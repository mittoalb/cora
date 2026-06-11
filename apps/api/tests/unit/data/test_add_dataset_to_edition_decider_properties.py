"""Property-based tests for `add_dataset_to_edition.decide`.

Universal claims across generated inputs:

  - state=None always raises EditionNotFoundError carrying the
    command's edition_id.
  - state.status != REGISTERED always raises
    EditionNotInRegisteredStateError.
  - context.dataset.status == DISCARDED always raises
    EditionCannotBindToDiscardedDatasetError.
  - dataset_id already in state.dataset_ids always raises
    EditionDatasetAlreadyMemberError.
  - Happy path emits a single EditionDatasetAdded with injected
    now / added_by.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
    EditionDatasetAdded,
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
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NON_REGISTERED_STATUS = st.sampled_from(
    [s for s in EditionStatus if s is not EditionStatus.REGISTERED]
)


def _dataset(dataset_id: UUID, *, status: DatasetStatus) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed"),
        uri=DatasetUri("s3://bucket/seed"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        status=status,
    )


def _edition(
    edition_id: UUID,
    *,
    dataset_ids: frozenset[UUID],
    status: EditionStatus,
    now: datetime,
) -> Edition:
    return Edition(
        id=edition_id,
        kind=EditionKind.ROCRATE,
        title=EditionTitle("E"),
        dataset_ids=dataset_ids,
        creators=(Creator(actor_id=ActorId(edition_id)),),
        registered_at=now,
        registered_by=ActorId(edition_id),
        status=status,
    )


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    dataset_id=st.uuids(),
    now=aware_datetimes(),
    added_by=st.uuids(),
)
def test_add_dataset_to_edition_state_none_always_raises_not_found(
    edition_id: UUID,
    dataset_id: UUID,
    now: datetime,
    added_by: UUID,
) -> None:
    ctx = AddDatasetToEditionContext(dataset=_dataset(dataset_id, status=DatasetStatus.REGISTERED))
    with pytest.raises(EditionNotFoundError) as exc:
        add_dataset_to_edition.decide(
            state=None,
            command=AddDatasetToEdition(edition_id=edition_id, dataset_id=dataset_id),
            context=ctx,
            now=now,
            added_by=ActorId(added_by),
        )
    assert exc.value.edition_id == edition_id


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    existing=st.uuids(),
    new_dataset_id=st.uuids(),
    bad_status=_NON_REGISTERED_STATUS,
    now=aware_datetimes(),
    added_by=st.uuids(),
)
def test_add_dataset_to_edition_non_registered_state_always_raises(
    edition_id: UUID,
    existing: UUID,
    new_dataset_id: UUID,
    bad_status: EditionStatus,
    now: datetime,
    added_by: UUID,
) -> None:
    state = _edition(
        edition_id,
        dataset_ids=frozenset({existing}),
        status=bad_status,
        now=now,
    )
    ctx = AddDatasetToEditionContext(
        dataset=_dataset(new_dataset_id, status=DatasetStatus.REGISTERED)
    )
    with pytest.raises(EditionNotInRegisteredStateError) as exc:
        add_dataset_to_edition.decide(
            state=state,
            command=AddDatasetToEdition(edition_id=edition_id, dataset_id=new_dataset_id),
            context=ctx,
            now=now,
            added_by=ActorId(added_by),
        )
    assert exc.value.current_status is bad_status


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    existing=st.uuids(),
    new_dataset_id=st.uuids(),
    now=aware_datetimes(),
    added_by=st.uuids(),
)
def test_add_dataset_to_edition_discarded_dataset_always_raises(
    edition_id: UUID,
    existing: UUID,
    new_dataset_id: UUID,
    now: datetime,
    added_by: UUID,
) -> None:
    state = _edition(
        edition_id,
        dataset_ids=frozenset({existing}),
        status=EditionStatus.REGISTERED,
        now=now,
    )
    ctx = AddDatasetToEditionContext(
        dataset=_dataset(new_dataset_id, status=DatasetStatus.DISCARDED)
    )
    with pytest.raises(EditionCannotBindToDiscardedDatasetError) as exc:
        add_dataset_to_edition.decide(
            state=state,
            command=AddDatasetToEdition(edition_id=edition_id, dataset_id=new_dataset_id),
            context=ctx,
            now=now,
            added_by=ActorId(added_by),
        )
    assert exc.value.dataset_id == new_dataset_id


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    existing=st.uuids(),
    now=aware_datetimes(),
    added_by=st.uuids(),
)
def test_add_dataset_to_edition_already_member_always_raises(
    edition_id: UUID,
    existing: UUID,
    now: datetime,
    added_by: UUID,
) -> None:
    state = _edition(
        edition_id,
        dataset_ids=frozenset({existing}),
        status=EditionStatus.REGISTERED,
        now=now,
    )
    ctx = AddDatasetToEditionContext(dataset=_dataset(existing, status=DatasetStatus.REGISTERED))
    with pytest.raises(EditionDatasetAlreadyMemberError) as exc:
        add_dataset_to_edition.decide(
            state=state,
            command=AddDatasetToEdition(edition_id=edition_id, dataset_id=existing),
            context=ctx,
            now=now,
            added_by=ActorId(added_by),
        )
    assert exc.value.dataset_id == existing


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    existing=st.uuids(),
    new_dataset_id=st.uuids(),
    now=aware_datetimes(),
    added_by=st.uuids(),
)
def test_add_dataset_to_edition_happy_path_emits_one_event(
    edition_id: UUID,
    existing: UUID,
    new_dataset_id: UUID,
    now: datetime,
    added_by: UUID,
) -> None:
    # Hypothesis can pick existing == new_dataset_id; skip those.
    if existing == new_dataset_id:
        return
    state = _edition(
        edition_id,
        dataset_ids=frozenset({existing}),
        status=EditionStatus.REGISTERED,
        now=now,
    )
    ctx = AddDatasetToEditionContext(
        dataset=_dataset(new_dataset_id, status=DatasetStatus.REGISTERED)
    )
    events = add_dataset_to_edition.decide(
        state=state,
        command=AddDatasetToEdition(edition_id=edition_id, dataset_id=new_dataset_id),
        context=ctx,
        now=now,
        added_by=ActorId(added_by),
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, EditionDatasetAdded)
    assert event.edition_id == edition_id
    assert event.dataset_id == new_dataset_id
    assert event.occurred_at == now
    assert event.added_by == ActorId(added_by)
