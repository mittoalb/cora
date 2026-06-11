"""Unit tests for the `remove_dataset_from_edition` application handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import UnauthorizedError
from cora.data.aggregates.edition import (
    EditionCannotBeEmptyError,
    EditionDatasetNotMemberError,
    EditionNotFoundError,
)
from cora.data.aggregates.edition.events import (
    EditionRegistered,
    event_type_name,
    to_payload,
)
from cora.data.features import remove_dataset_from_edition
from cora.data.features.remove_dataset_from_edition import RemoveDatasetFromEdition
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EDITION_ID = UUID("01900000-0000-7000-8000-000000ed1b01")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000ed1b02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DATASET_ID_A = UUID("01900000-0000-7000-8000-00000000dada")
_DATASET_ID_B = UUID("01900000-0000-7000-8000-00000000dadb")
_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000ac70")


async def _seed_edition(
    store: InMemoryEventStore,
    edition_id: UUID,
    *,
    dataset_ids: tuple[UUID, ...],
) -> None:
    registered = EditionRegistered(
        edition_id=edition_id,
        kind="ROCrate",
        title="E",
        dataset_ids=dataset_ids,
        creators=({"actor_id": ActorId(_ACTOR_ID), "affiliation": None},),
        publisher_facility_code=None,
        publication_year=None,
        license=None,
        occurred_at=_NOW,
        registered_by=ActorId(_PRINCIPAL_ID),
    )
    await store.append(
        stream_type="Edition",
        stream_id=edition_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(registered),
                payload=to_payload(registered),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="RegisterEdition",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


# ---------- Happy ----------


@pytest.mark.unit
async def test_handler_appends_dataset_removed_event_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_edition(store, _EDITION_ID, dataset_ids=(_DATASET_ID_A, _DATASET_ID_B))
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    await remove_dataset_from_edition.bind(deps)(
        RemoveDatasetFromEdition(edition_id=_EDITION_ID, dataset_id=_DATASET_ID_A),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Edition", _EDITION_ID)
    assert version == 2
    assert [e.event_type for e in events] == [
        "EditionRegistered",
        "EditionDatasetRemoved",
    ]
    payload = events[1].payload
    assert payload["edition_id"] == str(_EDITION_ID)
    assert payload["dataset_id"] == str(_DATASET_ID_A)
    assert payload["removed_by"] == str(_PRINCIPAL_ID)


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_edition(store, _EDITION_ID, dataset_ids=(_DATASET_ID_A, _DATASET_ID_B))
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await remove_dataset_from_edition.bind(deps)(
            RemoveDatasetFromEdition(edition_id=_EDITION_ID, dataset_id=_DATASET_ID_A),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Pre-load failure ----------


@pytest.mark.unit
async def test_handler_raises_edition_not_found_when_stream_empty() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(EditionNotFoundError):
        await remove_dataset_from_edition.bind(deps)(
            RemoveDatasetFromEdition(edition_id=uuid4(), dataset_id=_DATASET_ID_A),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Decider rejections via handler ----------


@pytest.mark.unit
async def test_handler_raises_when_dataset_not_member() -> None:
    store = InMemoryEventStore()
    await _seed_edition(store, _EDITION_ID, dataset_ids=(_DATASET_ID_A,))
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(EditionDatasetNotMemberError):
        await remove_dataset_from_edition.bind(deps)(
            RemoveDatasetFromEdition(edition_id=_EDITION_ID, dataset_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_when_removal_would_leave_empty() -> None:
    store = InMemoryEventStore()
    await _seed_edition(store, _EDITION_ID, dataset_ids=(_DATASET_ID_A,))
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(EditionCannotBeEmptyError):
        await remove_dataset_from_edition.bind(deps)(
            RemoveDatasetFromEdition(edition_id=_EDITION_ID, dataset_id=_DATASET_ID_A),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
