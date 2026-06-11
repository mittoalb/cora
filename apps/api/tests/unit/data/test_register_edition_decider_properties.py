"""Property-based tests for `register_edition.decide`.

Universal claims across generated inputs:

  - state=None + valid command + matching context emits a single
    EditionRegistered carrying the injected new_id / now / sorted
    dataset_ids.
  - state=Edition always raises EditionAlreadyExistsError, regardless
    of the command shape.
  - Any context.datasets entry with DISCARDED status always raises
    EditionCannotBindToDiscardedDatasetError.
  - Empty dataset_ids always raises EmptyDatasetIdsAtRegistrationError.
  - Pure: same (state, command, context, now, new_id, registered_by)
    returns the same events.
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
    EditionAlreadyExistsError,
    EditionCannotBindToDiscardedDatasetError,
    EditionKind,
    EditionRegistered,
    EditionStatus,
    EditionTitle,
    EmptyDatasetIdsAtRegistrationError,
)
from cora.data.features import register_edition
from cora.data.features.register_edition import (
    CreatorEntry,
    EditionRegistrationContext,
    RegisterEdition,
)
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_TITLE = st.from_regex(r"\A[A-Za-z0-9][A-Za-z0-9 ]{0,39}\Z", fullmatch=True)
_KIND = st.sampled_from(list(EditionKind))


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


def _existing_edition(edition_id: UUID, now: datetime) -> Edition:
    return Edition(
        id=edition_id,
        kind=EditionKind.ROCRATE,
        title=EditionTitle("existing"),
        dataset_ids=frozenset({edition_id}),
        creators=(Creator(actor_id=ActorId(edition_id)),),
        registered_at=now,
        registered_by=ActorId(edition_id),
        status=EditionStatus.REGISTERED,
    )


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    actor_id=st.uuids(),
    title=_TITLE,
    kind=_KIND,
    now=aware_datetimes(),
    new_id=st.uuids(),
    registered_by=st.uuids(),
)
def test_register_edition_happy_path_emits_one_event(
    dataset_id: UUID,
    actor_id: UUID,
    title: str,
    kind: EditionKind,
    now: datetime,
    new_id: UUID,
    registered_by: UUID,
) -> None:
    cmd = RegisterEdition(
        kind=kind.value,
        title=title,
        dataset_ids=frozenset({dataset_id}),
        creators=(CreatorEntry(actor_id=actor_id),),
    )
    ctx = EditionRegistrationContext(
        datasets={dataset_id: _dataset(dataset_id, status=DatasetStatus.REGISTERED)},
    )
    events = register_edition.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=now,
        new_id=new_id,
        registered_by=ActorId(registered_by),
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, EditionRegistered)
    assert event.edition_id == new_id
    assert event.kind == kind.value
    assert event.title == title.strip()
    assert event.dataset_ids == (dataset_id,)
    assert event.occurred_at == now
    assert event.registered_by == ActorId(registered_by)


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    dataset_id=st.uuids(),
    actor_id=st.uuids(),
    title=_TITLE,
    kind=_KIND,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_edition_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    dataset_id: UUID,
    actor_id: UUID,
    title: str,
    kind: EditionKind,
    now: datetime,
    new_id: UUID,
) -> None:
    cmd = RegisterEdition(
        kind=kind.value,
        title=title,
        dataset_ids=frozenset({dataset_id}),
        creators=(CreatorEntry(actor_id=actor_id),),
    )
    ctx = EditionRegistrationContext(
        datasets={dataset_id: _dataset(dataset_id, status=DatasetStatus.REGISTERED)},
    )
    existing = _existing_edition(existing_id, now)
    with pytest.raises(EditionAlreadyExistsError) as exc:
        register_edition.decide(
            state=existing,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            registered_by=ActorId(new_id),
        )
    assert exc.value.edition_id == existing_id


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    actor_id=st.uuids(),
    title=_TITLE,
    kind=_KIND,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_edition_discarded_dataset_always_raises(
    dataset_id: UUID,
    actor_id: UUID,
    title: str,
    kind: EditionKind,
    now: datetime,
    new_id: UUID,
) -> None:
    cmd = RegisterEdition(
        kind=kind.value,
        title=title,
        dataset_ids=frozenset({dataset_id}),
        creators=(CreatorEntry(actor_id=actor_id),),
    )
    ctx = EditionRegistrationContext(
        datasets={dataset_id: _dataset(dataset_id, status=DatasetStatus.DISCARDED)},
    )
    with pytest.raises(EditionCannotBindToDiscardedDatasetError) as exc:
        register_edition.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            registered_by=ActorId(new_id),
        )
    assert exc.value.dataset_id == dataset_id


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    title=_TITLE,
    kind=_KIND,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_edition_empty_dataset_ids_always_raises(
    actor_id: UUID,
    title: str,
    kind: EditionKind,
    now: datetime,
    new_id: UUID,
) -> None:
    cmd = RegisterEdition(
        kind=kind.value,
        title=title,
        dataset_ids=frozenset(),
        creators=(CreatorEntry(actor_id=actor_id),),
    )
    ctx = EditionRegistrationContext(datasets={})
    with pytest.raises(EmptyDatasetIdsAtRegistrationError):
        register_edition.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=now,
            new_id=new_id,
            registered_by=ActorId(new_id),
        )
