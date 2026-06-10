"""Unit tests for the `remove_dataset_from_edition` pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.edition import (
    Creator,
    Edition,
    EditionCannotBeEmptyError,
    EditionDatasetNotMemberError,
    EditionKind,
    EditionNotFoundError,
    EditionNotInRegisteredStateError,
    EditionStatus,
    EditionTitle,
)
from cora.data.features import remove_dataset_from_edition
from cora.data.features.remove_dataset_from_edition import RemoveDatasetFromEdition
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_REMOVED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000aa"))


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
        registered_by=_REMOVED_BY,
        status=status,
    )


# ---------- Happy ----------


@pytest.mark.unit
def test_decide_emits_dataset_removed() -> None:
    edition_id = uuid4()
    keep = uuid4()
    drop = uuid4()
    state = _edition(edition_id, dataset_ids=frozenset({keep, drop}))
    events = remove_dataset_from_edition.decide(
        state=state,
        command=RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=drop),
        now=_NOW,
        removed_by=_REMOVED_BY,
    )
    assert len(events) == 1
    event = events[0]
    assert event.edition_id == edition_id
    assert event.dataset_id == drop
    assert event.occurred_at == _NOW
    assert event.removed_by == _REMOVED_BY


# ---------- Rejections ----------


@pytest.mark.unit
def test_decide_raises_when_state_is_none() -> None:
    edition_id = uuid4()
    drop = uuid4()
    with pytest.raises(EditionNotFoundError) as exc:
        remove_dataset_from_edition.decide(
            state=None,
            command=RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=drop),
            now=_NOW,
            removed_by=_REMOVED_BY,
        )
    assert exc.value.edition_id == edition_id


@pytest.mark.unit
def test_decide_raises_when_edition_not_in_registered_state() -> None:
    edition_id = uuid4()
    keep = uuid4()
    drop = uuid4()
    state = _edition(edition_id, dataset_ids=frozenset({keep, drop}), status=EditionStatus.SEALED)
    with pytest.raises(EditionNotInRegisteredStateError):
        remove_dataset_from_edition.decide(
            state=state,
            command=RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=drop),
            now=_NOW,
            removed_by=_REMOVED_BY,
        )


@pytest.mark.unit
def test_decide_raises_when_dataset_not_member() -> None:
    edition_id = uuid4()
    keep = uuid4()
    drop = uuid4()
    state = _edition(edition_id, dataset_ids=frozenset({keep}))
    with pytest.raises(EditionDatasetNotMemberError) as exc:
        remove_dataset_from_edition.decide(
            state=state,
            command=RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=drop),
            now=_NOW,
            removed_by=_REMOVED_BY,
        )
    assert exc.value.dataset_id == drop


@pytest.mark.unit
def test_decide_raises_when_removal_would_leave_empty() -> None:
    edition_id = uuid4()
    only = uuid4()
    state = _edition(edition_id, dataset_ids=frozenset({only}))
    with pytest.raises(EditionCannotBeEmptyError) as exc:
        remove_dataset_from_edition.decide(
            state=state,
            command=RemoveDatasetFromEdition(edition_id=edition_id, dataset_id=only),
            now=_NOW,
            removed_by=_REMOVED_BY,
        )
    assert exc.value.edition_id == edition_id
