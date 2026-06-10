"""Unit tests for the `register_edition` slice's pure decider.

Genesis-style: state must be None (otherwise EditionAlreadyExistsError);
VOs validate input; context carries pre-loaded Datasets keyed by id.
"""

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
    EDITION_CREATORS_MAX,
    EDITION_PUBLICATION_YEAR_FUTURE_BUDGET,
    EDITION_PUBLICATION_YEAR_MIN,
    Creator,
    Edition,
    EditionAlreadyExistsError,
    EditionCannotBindToDiscardedDatasetError,
    EditionKind,
    EditionStatus,
    EditionTitle,
    EmptyDatasetIdsAtRegistrationError,
    InvalidCreatorsError,
    InvalidEditionKindError,
    InvalidEditionTitleError,
    InvalidPublicationYearError,
    InvalidSpdxIdentifierError,
)
from cora.data.features import register_edition
from cora.data.features.register_edition import (
    CreatorEntry,
    EditionRegistrationContext,
    RegisterEdition,
)
from cora.shared.identity import ActorId

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000aa"))
_DATASET_ID = UUID("01900000-0000-7000-8000-00000000da7a")
_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000ac70")


def _dataset(
    dataset_id: UUID,
    *,
    status: DatasetStatus = DatasetStatus.REGISTERED,
) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed-dataset"),
        uri=DatasetUri("s3://bucket/seed"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        status=status,
    )


def _good_command(**overrides: object) -> RegisterEdition:
    base: dict[str, object] = {
        "kind": "ROCrate",
        "title": "Test Edition",
        "dataset_ids": frozenset({_DATASET_ID}),
        "creators": (CreatorEntry(actor_id=_ACTOR_ID, affiliation="ANL"),),
        "license": None,
        "publication_year": None,
        "publisher_facility_code": None,
    }
    base.update(overrides)
    return RegisterEdition(**base)  # type: ignore[arg-type]


def _good_context(cmd: RegisterEdition) -> EditionRegistrationContext:
    return EditionRegistrationContext(
        datasets={d: _dataset(d) for d in cmd.dataset_ids},
    )


def _existing_edition(edition_id: UUID) -> Edition:
    return Edition(
        id=edition_id,
        kind=EditionKind.ROCRATE,
        title=EditionTitle("Existing"),
        dataset_ids=frozenset({uuid4()}),
        creators=(Creator(actor_id=ActorId(uuid4())),),
        registered_at=_NOW,
        registered_by=_REGISTERED_BY,
        status=EditionStatus.REGISTERED,
    )


# ---------- Happy path ----------


@pytest.mark.unit
def test_decide_emits_edition_registered_with_all_fields() -> None:
    new_id = uuid4()
    cmd = _good_command()
    events = register_edition.decide(
        state=None,
        command=cmd,
        context=_good_context(cmd),
        now=_NOW,
        new_id=new_id,
        registered_by=_REGISTERED_BY,
    )
    assert len(events) == 1
    event = events[0]
    assert event.edition_id == new_id
    assert event.kind == "ROCrate"
    assert event.title == "Test Edition"
    assert event.dataset_ids == (_DATASET_ID,)
    assert event.creators == ({"actor_id": ActorId(_ACTOR_ID), "affiliation": "ANL"},)
    assert event.license is None
    assert event.publication_year is None
    assert event.publisher_facility_code is None
    assert event.occurred_at == _NOW
    assert event.registered_by == _REGISTERED_BY


@pytest.mark.unit
def test_decide_sorts_dataset_ids_on_wire() -> None:
    d1 = UUID("01900000-0000-7000-8000-00000000da01")
    d2 = UUID("01900000-0000-7000-8000-00000000da02")
    d3 = UUID("01900000-0000-7000-8000-00000000da03")
    cmd = _good_command(dataset_ids=frozenset({d3, d1, d2}))
    ctx = EditionRegistrationContext(
        datasets={d1: _dataset(d1), d2: _dataset(d2), d3: _dataset(d3)},
    )
    events = register_edition.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].dataset_ids == (d1, d2, d3)


@pytest.mark.unit
def test_decide_accepts_supplied_license_and_publication_year() -> None:
    cmd = _good_command(license="CC-BY-4.0", publication_year=2024)
    events = register_edition.decide(
        state=None,
        command=cmd,
        context=_good_context(cmd),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].license == "CC-BY-4.0"
    assert events[0].publication_year == 2024


@pytest.mark.unit
def test_decide_trims_title_via_value_object() -> None:
    cmd = _good_command(title="  Spaced Title  ")
    events = register_edition.decide(
        state=None,
        command=cmd,
        context=_good_context(cmd),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_REGISTERED_BY,
    )
    assert events[0].title == "Spaced Title"


# ---------- Field validation ----------


@pytest.mark.unit
def test_decide_raises_invalid_title_for_empty() -> None:
    cmd = _good_command(title="   ")
    with pytest.raises(InvalidEditionTitleError):
        register_edition.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_kind_for_unknown() -> None:
    cmd = _good_command(kind="JunkKind")
    with pytest.raises(InvalidEditionKindError):
        register_edition.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_license_for_bad_chars() -> None:
    cmd = _good_command(license="CC BY 4.0")
    with pytest.raises(InvalidSpdxIdentifierError):
        register_edition.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_publication_year_for_too_old() -> None:
    cmd = _good_command(publication_year=EDITION_PUBLICATION_YEAR_MIN - 1)
    with pytest.raises(InvalidPublicationYearError):
        register_edition.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_publication_year_for_too_new() -> None:
    too_new = _NOW.year + EDITION_PUBLICATION_YEAR_FUTURE_BUDGET + 1
    cmd = _good_command(publication_year=too_new)
    with pytest.raises(InvalidPublicationYearError):
        register_edition.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_creators_for_duplicate_actor_id() -> None:
    dupe = ActorId(uuid4())
    cmd = _good_command(
        creators=(
            CreatorEntry(actor_id=dupe, affiliation=None),
            CreatorEntry(actor_id=dupe, affiliation="ANL"),
        )
    )
    with pytest.raises(InvalidCreatorsError):
        register_edition.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_creators_for_oversize_tuple() -> None:
    creators = tuple(
        CreatorEntry(actor_id=ActorId(uuid4())) for _ in range(EDITION_CREATORS_MAX + 1)
    )
    cmd = _good_command(creators=creators)
    with pytest.raises(InvalidCreatorsError):
        register_edition.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_creators_for_empty_affiliation() -> None:
    cmd = _good_command(
        creators=(CreatorEntry(actor_id=ActorId(uuid4()), affiliation="   "),),
    )
    with pytest.raises(InvalidCreatorsError):
        register_edition.decide(
            state=None,
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


# ---------- dataset_ids cardinality ----------


@pytest.mark.unit
def test_decide_raises_empty_dataset_ids() -> None:
    cmd = _good_command(dataset_ids=frozenset[UUID]())
    with pytest.raises(EmptyDatasetIdsAtRegistrationError):
        register_edition.decide(
            state=None,
            command=cmd,
            context=EditionRegistrationContext(datasets={}),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )


# ---------- Cross-aggregate guard ----------


@pytest.mark.unit
def test_decide_raises_on_discarded_dataset() -> None:
    cmd = _good_command()
    ctx = EditionRegistrationContext(
        datasets={_DATASET_ID: _dataset(_DATASET_ID, status=DatasetStatus.DISCARDED)},
    )
    with pytest.raises(EditionCannotBindToDiscardedDatasetError) as exc:
        register_edition.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
    assert exc.value.dataset_id == _DATASET_ID


# ---------- Genesis guard ----------


@pytest.mark.unit
def test_decide_raises_already_exists_when_state_not_none() -> None:
    existing_id = uuid4()
    cmd = _good_command()
    with pytest.raises(EditionAlreadyExistsError) as exc:
        register_edition.decide(
            state=_existing_edition(existing_id),
            command=cmd,
            context=_good_context(cmd),
            now=_NOW,
            new_id=uuid4(),
            registered_by=_REGISTERED_BY,
        )
    assert exc.value.edition_id == existing_id


# ---------- Purity ----------


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    cmd = _good_command()
    ctx = _good_context(cmd)
    first = register_edition.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=new_id,
        registered_by=_REGISTERED_BY,
    )
    second = register_edition.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=new_id,
        registered_by=_REGISTERED_BY,
    )
    assert first == second
