"""Unit tests for the `seal_edition` pure decider.

Tests exhaustively cover the L15 firing order via direct decider
calls with hand-built `SealEditionContext` instances.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Intent,
)
from cora.data.aggregates.dataset.state import (
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
    EditionCannotSealError,
    EditionCannotSealOnDiscardedDatasetError,
    EditionDatasetDistributionNotFoundError,
    EditionDatasetsNotAllProductionError,
    EditionKind,
    EditionLicenseRequiredForKindError,
    EditionRequiresAtLeastOneDatasetError,
    EditionSealed,
    EditionStatus,
    EditionTitle,
)
from cora.data.features.seal_edition.command import SealEdition
from cora.data.features.seal_edition.context import SealEditionContext
from cora.data.features.seal_edition.decider import decide
from cora.shared.identity import ActorId

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EDITION_ID = UUID("01900000-0000-7000-8000-00000000ed01")
_DATASET_A = UUID("01900000-0000-7000-8000-00000000da01")
_DATASET_B = UUID("01900000-0000-7000-8000-00000000da02")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac70"))
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac71"))
_SEAL_HASH = "deadbeef" * 8


def _dataset(
    dataset_id: UUID,
    *,
    intent: Intent = Intent.PRODUCTION,
    status: DatasetStatus = DatasetStatus.REGISTERED,
) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("a"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        intent=intent,
        status=status,
    )


def _edition(
    *,
    status: EditionStatus = EditionStatus.REGISTERED,
    kind: EditionKind = EditionKind.ROCRATE,
    dataset_ids: frozenset[UUID] = frozenset({_DATASET_A}),
) -> Edition:
    return Edition(
        id=_EDITION_ID,
        kind=kind,
        title=EditionTitle("Pilot"),
        dataset_ids=dataset_ids,
        creators=(Creator(actor_id=_ACTOR_ID, affiliation="ANL"),),
        registered_at=_NOW,
        registered_by=_PRINCIPAL_ID,
        status=status,
    )


def _context(
    *,
    datasets: dict[UUID, Dataset] | None = None,
    canonical_ids: frozenset[UUID] | None = None,
    publisher_facility_code: str = "cora",
    publication_year: int = 2026,
    license: str | None = None,
) -> SealEditionContext:
    if datasets is None:
        datasets = {_DATASET_A: _dataset(_DATASET_A)}
    if canonical_ids is None:
        canonical_ids = frozenset(datasets.keys())
    return SealEditionContext(
        datasets=datasets,
        dataset_ids_with_canonical_distribution=canonical_ids,
        publisher_facility_code=publisher_facility_code,
        publication_year=publication_year,
        license=license,
        content_hash=_SEAL_HASH,
    )


@pytest.mark.unit
def test_decider_emits_edition_sealed_on_happy_path() -> None:
    events = decide(
        state=_edition(),
        command=SealEdition(edition_id=_EDITION_ID),
        context=_context(),
        now=_NOW,
        sealed_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    sealed = events[0]
    assert isinstance(sealed, EditionSealed)
    assert sealed.edition_id == _EDITION_ID
    assert sealed.content_hash == _SEAL_HASH
    assert sealed.publisher_facility_code == "cora"
    assert sealed.publication_year == 2026
    assert sealed.sealed_dataset_ids == (_DATASET_A,)
    assert sealed.sealed_by == _PRINCIPAL_ID


@pytest.mark.unit
def test_decider_rejects_non_registered_status() -> None:
    with pytest.raises(EditionCannotSealError) as exc:
        decide(
            state=_edition(status=EditionStatus.SEALED),
            command=SealEdition(edition_id=_EDITION_ID),
            context=_context(),
            now=_NOW,
            sealed_by=_PRINCIPAL_ID,
        )
    assert exc.value.current_status is EditionStatus.SEALED


@pytest.mark.unit
def test_decider_rejects_empty_dataset_ids() -> None:
    with pytest.raises(EditionRequiresAtLeastOneDatasetError):
        decide(
            state=_edition(dataset_ids=frozenset()),
            command=SealEdition(edition_id=_EDITION_ID),
            context=_context(datasets={}, canonical_ids=frozenset()),
            now=_NOW,
            sealed_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decider_rejects_discarded_member_dataset() -> None:
    discarded_dataset = _dataset(_DATASET_A, status=DatasetStatus.DISCARDED)
    with pytest.raises(EditionCannotSealOnDiscardedDatasetError) as exc:
        decide(
            state=_edition(),
            command=SealEdition(edition_id=_EDITION_ID),
            context=_context(datasets={_DATASET_A: discarded_dataset}),
            now=_NOW,
            sealed_by=_PRINCIPAL_ID,
        )
    assert _DATASET_A in exc.value.dataset_ids


@pytest.mark.unit
def test_decider_rejects_non_production_member_dataset() -> None:
    trial_dataset = _dataset(_DATASET_A, intent=Intent.TRIAL)
    with pytest.raises(EditionDatasetsNotAllProductionError) as exc:
        decide(
            state=_edition(),
            command=SealEdition(edition_id=_EDITION_ID),
            context=_context(datasets={_DATASET_A: trial_dataset}),
            now=_NOW,
            sealed_by=_PRINCIPAL_ID,
        )
    assert exc.value.offenders == ((_DATASET_A, "Trial"),)


@pytest.mark.unit
def test_decider_rejects_missing_canonical_distribution() -> None:
    with pytest.raises(EditionDatasetDistributionNotFoundError) as exc:
        decide(
            state=_edition(),
            command=SealEdition(edition_id=_EDITION_ID),
            context=_context(canonical_ids=frozenset()),
            now=_NOW,
            sealed_by=_PRINCIPAL_ID,
        )
    assert _DATASET_A in exc.value.dataset_ids


@pytest.mark.unit
def test_decider_requires_license_for_datacite_kind() -> None:
    with pytest.raises(EditionLicenseRequiredForKindError):
        decide(
            state=_edition(kind=EditionKind.DATACITE),
            command=SealEdition(edition_id=_EDITION_ID),
            context=_context(license=None),
            now=_NOW,
            sealed_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decider_requires_license_for_croissant_kind() -> None:
    with pytest.raises(EditionLicenseRequiredForKindError):
        decide(
            state=_edition(kind=EditionKind.CROISSANT),
            command=SealEdition(edition_id=_EDITION_ID),
            context=_context(license=None),
            now=_NOW,
            sealed_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_decider_accepts_license_for_datacite_kind() -> None:
    events = decide(
        state=_edition(kind=EditionKind.DATACITE),
        command=SealEdition(edition_id=_EDITION_ID),
        context=_context(license="CC-BY-4.0"),
        now=_NOW,
        sealed_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert isinstance(events[0], EditionSealed)
    assert events[0].license == "CC-BY-4.0"


@pytest.mark.unit
def test_decider_orders_offenders_deterministically() -> None:
    other_dataset = uuid4()
    trial_a = _dataset(_DATASET_A, intent=Intent.TRIAL)
    trial_b = _dataset(other_dataset, intent=Intent.RETRACTED)
    with pytest.raises(EditionDatasetsNotAllProductionError) as exc:
        decide(
            state=_edition(dataset_ids=frozenset({_DATASET_A, other_dataset})),
            command=SealEdition(edition_id=_EDITION_ID),
            context=_context(
                datasets={_DATASET_A: trial_a, other_dataset: trial_b},
                canonical_ids=frozenset({_DATASET_A, other_dataset}),
            ),
            now=_NOW,
            sealed_by=_PRINCIPAL_ID,
        )
    # Sorted by UUID
    ids = [pair[0] for pair in exc.value.offenders]
    assert ids == sorted(ids)
