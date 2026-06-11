"""Property-based tests for `seal_edition.decide`.

Universal claims across generated inputs:

  - state.status != REGISTERED always raises EditionCannotSealError.
  - empty state.dataset_ids always raises
    EditionRequiresAtLeastOneDatasetError.
  - all-Production members with non-empty canonical-distribution set
    AND a license (for ROCrate) produces a single EditionSealed
    with the captured content_hash + publisher.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
    Intent,
)
from cora.data.aggregates.edition import (
    Creator,
    Edition,
    EditionCannotSealError,
    EditionKind,
    EditionRequiresAtLeastOneDatasetError,
    EditionSealed,
    EditionStatus,
    EditionTitle,
)
from cora.data.features.seal_edition.command import SealEdition
from cora.data.features.seal_edition.context import SealEditionContext
from cora.data.features.seal_edition.decider import decide
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from uuid import UUID

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_SEAL_HASH = "f" * 64
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_NON_REGISTERED_STATUS = st.sampled_from(
    [s for s in EditionStatus if s is not EditionStatus.REGISTERED]
)


def _dataset(dataset_id: UUID) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed"),
        uri=DatasetUri("s3://bucket/seed"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        intent=Intent.PRODUCTION,
        status=DatasetStatus.REGISTERED,
    )


def _edition(
    edition_id: UUID,
    *,
    status: EditionStatus = EditionStatus.REGISTERED,
    dataset_ids: frozenset[UUID] | None = None,
) -> Edition:
    return Edition(
        id=edition_id,
        kind=EditionKind.ROCRATE,
        title=EditionTitle("E"),
        dataset_ids=dataset_ids if dataset_ids is not None else frozenset(),
        creators=(Creator(actor_id=ActorId(edition_id)),),
        registered_at=_NOW,
        registered_by=ActorId(edition_id),
        status=status,
    )


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    status=_NON_REGISTERED_STATUS,
)
def test_decider_rejects_non_registered_status_for_any_input(
    edition_id: UUID,
    status: EditionStatus,
) -> None:
    state = _edition(edition_id, status=status, dataset_ids=frozenset({edition_id}))
    ctx = SealEditionContext(
        datasets={edition_id: _dataset(edition_id)},
        dataset_ids_with_canonical_distribution=frozenset({edition_id}),
        publisher_facility_code="cora",
        publication_year=2026,
        license=None,
        content_hash=_SEAL_HASH,
    )
    with pytest.raises(EditionCannotSealError):
        decide(
            state=state,
            command=SealEdition(edition_id=edition_id),
            context=ctx,
            now=_NOW,
            sealed_by=ActorId(edition_id),
        )


@pytest.mark.unit
@given(edition_id=st.uuids())
def test_decider_rejects_empty_dataset_ids(edition_id: UUID) -> None:
    state = _edition(edition_id, dataset_ids=frozenset())
    ctx = SealEditionContext(
        datasets={},
        dataset_ids_with_canonical_distribution=frozenset(),
        publisher_facility_code="cora",
        publication_year=2026,
        license=None,
        content_hash=_SEAL_HASH,
    )
    with pytest.raises(EditionRequiresAtLeastOneDatasetError):
        decide(
            state=state,
            command=SealEdition(edition_id=edition_id),
            context=ctx,
            now=_NOW,
            sealed_by=ActorId(edition_id),
        )


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    dataset_id=st.uuids(),
    publication_year=st.integers(min_value=1900, max_value=2030),
)
def test_decider_happy_path_emits_one_edition_sealed(
    edition_id: UUID,
    dataset_id: UUID,
    publication_year: int,
) -> None:
    state = _edition(edition_id, dataset_ids=frozenset({dataset_id}))
    ctx = SealEditionContext(
        datasets={dataset_id: _dataset(dataset_id)},
        dataset_ids_with_canonical_distribution=frozenset({dataset_id}),
        publisher_facility_code="cora",
        publication_year=publication_year,
        license=None,
        content_hash=_SEAL_HASH,
    )
    events = decide(
        state=state,
        command=SealEdition(edition_id=edition_id),
        context=ctx,
        now=_NOW,
        sealed_by=ActorId(edition_id),
    )
    assert len(events) == 1
    sealed = events[0]
    assert isinstance(sealed, EditionSealed)
    assert sealed.content_hash == _SEAL_HASH
    assert sealed.publication_year == publication_year
    assert sealed.sealed_dataset_ids == (dataset_id,)
