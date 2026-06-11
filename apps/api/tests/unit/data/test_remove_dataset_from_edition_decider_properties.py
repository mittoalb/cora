"""Property-based tests for `remove_dataset_from_edition.decide`.

Universal claims across generated inputs:

  - state=None always raises EditionNotFoundError.
  - state.status != REGISTERED always raises
    EditionNotInRegisteredStateError.
  - dataset_id NOT in state.dataset_ids always raises
    EditionDatasetNotMemberError.
  - Removing the last member always raises EditionCannotBeEmptyError.
  - Happy path emits a single EditionDatasetRemoved with injected
    now / removed_by.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.data.aggregates.edition import (
    Creator,
    Edition,
    EditionCannotBeEmptyError,
    EditionDatasetNotMemberError,
    EditionDatasetRemoved,
    EditionKind,
    EditionNotFoundError,
    EditionNotInRegisteredStateError,
    EditionStatus,
    EditionTitle,
)
from cora.data.features import remove_dataset_from_edition
from cora.data.features.remove_dataset_from_edition import RemoveDatasetFromEdition
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NON_REGISTERED_STATUS = st.sampled_from(
    [s for s in EditionStatus if s is not EditionStatus.REGISTERED]
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
    removed_by=st.uuids(),
)
def test_remove_dataset_state_none_always_raises_not_found(
    edition_id: UUID,
    dataset_id: UUID,
    now: datetime,
    removed_by: UUID,
) -> None:
    with pytest.raises(EditionNotFoundError) as exc:
        remove_dataset_from_edition.decide(
            state=None,
            command=RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=dataset_id),
            now=now,
            removed_by=ActorId(removed_by),
        )
    assert exc.value.edition_id == edition_id


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    first=st.uuids(),
    second=st.uuids(),
    bad_status=_NON_REGISTERED_STATUS,
    now=aware_datetimes(),
    removed_by=st.uuids(),
)
def test_remove_dataset_non_registered_state_always_raises(
    edition_id: UUID,
    first: UUID,
    second: UUID,
    bad_status: EditionStatus,
    now: datetime,
    removed_by: UUID,
) -> None:
    if first == second:
        return
    state = _edition(
        edition_id,
        dataset_ids=frozenset({first, second}),
        status=bad_status,
        now=now,
    )
    with pytest.raises(EditionNotInRegisteredStateError) as exc:
        remove_dataset_from_edition.decide(
            state=state,
            command=RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=first),
            now=now,
            removed_by=ActorId(removed_by),
        )
    assert exc.value.current_status is bad_status


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    existing=st.uuids(),
    non_member=st.uuids(),
    now=aware_datetimes(),
    removed_by=st.uuids(),
)
def test_remove_dataset_not_member_always_raises(
    edition_id: UUID,
    existing: UUID,
    non_member: UUID,
    now: datetime,
    removed_by: UUID,
) -> None:
    if existing == non_member:
        return
    state = _edition(
        edition_id,
        dataset_ids=frozenset({existing}),
        status=EditionStatus.REGISTERED,
        now=now,
    )
    with pytest.raises(EditionDatasetNotMemberError) as exc:
        remove_dataset_from_edition.decide(
            state=state,
            command=RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=non_member),
            now=now,
            removed_by=ActorId(removed_by),
        )
    assert exc.value.dataset_id == non_member


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    only=st.uuids(),
    now=aware_datetimes(),
    removed_by=st.uuids(),
)
def test_remove_last_dataset_always_raises_cannot_be_empty(
    edition_id: UUID,
    only: UUID,
    now: datetime,
    removed_by: UUID,
) -> None:
    state = _edition(
        edition_id,
        dataset_ids=frozenset({only}),
        status=EditionStatus.REGISTERED,
        now=now,
    )
    with pytest.raises(EditionCannotBeEmptyError) as exc:
        remove_dataset_from_edition.decide(
            state=state,
            command=RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=only),
            now=now,
            removed_by=ActorId(removed_by),
        )
    assert exc.value.edition_id == edition_id


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    first=st.uuids(),
    second=st.uuids(),
    now=aware_datetimes(),
    removed_by=st.uuids(),
)
def test_remove_dataset_happy_path_emits_one_event(
    edition_id: UUID,
    first: UUID,
    second: UUID,
    now: datetime,
    removed_by: UUID,
) -> None:
    if first == second:
        return
    state = _edition(
        edition_id,
        dataset_ids=frozenset({first, second}),
        status=EditionStatus.REGISTERED,
        now=now,
    )
    events = remove_dataset_from_edition.decide(
        state=state,
        command=RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=first),
        now=now,
        removed_by=ActorId(removed_by),
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, EditionDatasetRemoved)
    assert event.edition_id == edition_id
    assert event.dataset_id == first
    assert event.occurred_at == now
    assert event.removed_by == ActorId(removed_by)
