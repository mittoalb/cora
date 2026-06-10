"""Unit tests for the Edition evolver: per-event fold semantics + carry-forward.

Verifies every transition arm preserves prior genesis / sealed / published
fields so additive-state contracts hold across the full FSM walk.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from cora.data.aggregates.edition.events import (
    EditionDatasetAdded,
    EditionDatasetRemoved,
    EditionPublished,
    EditionRegistered,
    EditionSealed,
    EditionWithdrawn,
)
from cora.data.aggregates.edition.evolver import fold
from cora.data.aggregates.edition.state import EditionKind, EditionStatus
from cora.shared.identifier import PersistentIdentifierScheme
from cora.shared.identity import ActorId

_ACTOR = ActorId(uuid4())
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _registered(
    edition_id: UUID,
    *,
    dataset_ids: tuple[UUID, ...],
    kind: str = "ROCrate",
) -> EditionRegistered:
    return EditionRegistered(
        edition_id=edition_id,
        kind=kind,
        title="My Edition",
        dataset_ids=dataset_ids,
        creators=({"actor_id": _ACTOR, "affiliation": "ANL"},),
        publisher_facility_code=None,
        publication_year=None,
        license=None,
        occurred_at=_NOW,
        registered_by=_ACTOR,
    )


def test_fold_genesis_yields_registered_state() -> None:
    edition_id = uuid4()
    dataset_id = uuid4()
    state = fold([_registered(edition_id, dataset_ids=(dataset_id,))])
    assert state is not None
    assert state.id == edition_id
    assert state.status == EditionStatus.REGISTERED
    assert state.dataset_ids == frozenset({dataset_id})
    assert state.kind == EditionKind.ROCRATE
    assert state.content_hash is None
    assert state.external_pid is None


def test_fold_add_remove_dataset_mutates_membership() -> None:
    edition_id = uuid4()
    d1, d2 = uuid4(), uuid4()
    state = fold(
        [
            _registered(edition_id, dataset_ids=(d1,)),
            EditionDatasetAdded(edition_id, d2, _NOW, _ACTOR),
            EditionDatasetRemoved(edition_id, d1, _NOW, _ACTOR),
        ]
    )
    assert state is not None
    assert state.dataset_ids == frozenset({d2})
    assert state.status == EditionStatus.REGISTERED


def test_fold_sealed_freezes_content_hash_and_membership() -> None:
    edition_id = uuid4()
    d1, d2 = uuid4(), uuid4()
    sealed_hash = "a" * 64
    state = fold(
        [
            _registered(edition_id, dataset_ids=(d1,)),
            EditionDatasetAdded(edition_id, d2, _NOW, _ACTOR),
            EditionSealed(
                edition_id=edition_id,
                content_hash=sealed_hash,
                publisher_facility_code="aps",
                publication_year=2026,
                license="CC-BY-4.0",
                sealed_dataset_ids=(d1, d2),
                occurred_at=_NOW,
                sealed_by=_ACTOR,
            ),
        ]
    )
    assert state is not None
    assert state.status == EditionStatus.SEALED
    assert state.content_hash == sealed_hash
    assert state.publication_year == 2026
    assert state.license is not None
    assert state.license.value == "CC-BY-4.0"
    assert state.dataset_ids == frozenset({d1, d2})
    assert state.publisher_facility_code is not None
    assert state.publisher_facility_code.value == "aps"


def test_fold_published_attaches_external_pid_and_preserves_content_hash() -> None:
    edition_id = uuid4()
    d1 = uuid4()
    sealed_hash = "b" * 64
    state = fold(
        [
            _registered(edition_id, dataset_ids=(d1,)),
            EditionSealed(
                edition_id=edition_id,
                content_hash=sealed_hash,
                publisher_facility_code="aps",
                publication_year=2026,
                license=None,
                sealed_dataset_ids=(d1,),
                occurred_at=_NOW,
                sealed_by=_ACTOR,
            ),
            EditionPublished(
                edition_id=edition_id,
                external_pid_scheme="DOI",
                external_pid_value="10.0000/cora-stub/x",
                published_content_hash="c" * 64,
                occurred_at=_NOW,
                published_by=_ACTOR,
            ),
        ]
    )
    assert state is not None
    assert state.status == EditionStatus.PUBLISHED
    assert state.content_hash == sealed_hash  # carry-forward, NOT overwritten
    assert state.external_pid is not None
    assert state.external_pid.scheme == PersistentIdentifierScheme.DOI
    assert state.external_pid.value == "10.0000/cora-stub/x"


def test_fold_withdrawn_attaches_reason_and_preserves_pid() -> None:
    edition_id = uuid4()
    d1 = uuid4()
    state = fold(
        [
            _registered(edition_id, dataset_ids=(d1,)),
            EditionSealed(
                edition_id=edition_id,
                content_hash="d" * 64,
                publisher_facility_code="aps",
                publication_year=2026,
                license=None,
                sealed_dataset_ids=(d1,),
                occurred_at=_NOW,
                sealed_by=_ACTOR,
            ),
            EditionPublished(
                edition_id=edition_id,
                external_pid_scheme="DOI",
                external_pid_value="10.0000/cora-stub/y",
                published_content_hash="e" * 64,
                occurred_at=_NOW,
                published_by=_ACTOR,
            ),
            EditionWithdrawn(
                edition_id=edition_id,
                withdrawal_reason="audit-found duplicate",
                occurred_at=_NOW,
                withdrawn_by=_ACTOR,
            ),
        ]
    )
    assert state is not None
    assert state.status == EditionStatus.WITHDRAWN
    assert state.withdrawal_reason == "audit-found duplicate"
    assert state.external_pid is not None  # tombstoned, NOT deleted
    assert state.content_hash == "d" * 64
