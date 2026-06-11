"""Unit tests for the `publish_edition` pure decider.

Covers the decider-tier firing order via direct decider calls with
hand-built `PublishEditionContext` instances: status guard
(EditionCannotPublishError on non-Sealed sources), the defensive
content_hash invariant, and the happy-path EditionPublished echoing
the context's minted PID + published_content_hash.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.data.aggregates.edition import (
    Creator,
    Edition,
    EditionCannotPublishError,
    EditionKind,
    EditionPublished,
    EditionPublishedWithoutContentHashError,
    EditionStatus,
    EditionTitle,
)
from cora.data.features.publish_edition.command import PublishEdition
from cora.data.features.publish_edition.context import PublishEditionContext
from cora.data.features.publish_edition.decider import decide
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import PersistentIdentifier, PersistentIdentifierScheme
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EDITION_ID = UUID("01900000-0000-7000-8000-00000000ed01")
_DATASET_A = UUID("01900000-0000-7000-8000-00000000da01")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac70"))
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac71"))
_SEAL_HASH = "deadbeef" * 8
_PUBLISHED_HASH = "feedface" * 8
_MINTED_PID = PersistentIdentifier(
    scheme=PersistentIdentifierScheme.DOI,
    value="10.0000/cora-stub/01900000-0000-7000-8000-00000000ed01",
)


def _edition(
    *,
    status: EditionStatus = EditionStatus.SEALED,
    content_hash: str | None = _SEAL_HASH,
) -> Edition:
    return Edition(
        id=_EDITION_ID,
        kind=EditionKind.ROCRATE,
        title=EditionTitle("Pilot"),
        dataset_ids=frozenset({_DATASET_A}),
        creators=(Creator(actor_id=_ACTOR_ID, affiliation="ANL"),),
        registered_at=_NOW,
        registered_by=_PRINCIPAL_ID,
        status=status,
        publisher_facility_code=FacilityCode("cora"),
        publication_year=2026,
        content_hash=content_hash,
        sealed_at=_NOW,
        sealed_by=_PRINCIPAL_ID,
    )


def _context(
    *,
    external_pid: PersistentIdentifier = _MINTED_PID,
    published_content_hash: str = _PUBLISHED_HASH,
) -> PublishEditionContext:
    return PublishEditionContext(
        external_pid=external_pid,
        published_content_hash=published_content_hash,
    )


@pytest.mark.unit
def test_decider_emits_edition_published_on_happy_path() -> None:
    events = decide(
        state=_edition(),
        command=PublishEdition(edition_id=_EDITION_ID),
        context=_context(),
        now=_NOW,
        published_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    published = events[0]
    assert isinstance(published, EditionPublished)
    assert published.edition_id == _EDITION_ID
    assert published.external_pid_scheme == "DOI"
    assert published.external_pid_value == _MINTED_PID.value
    assert published.published_content_hash == _PUBLISHED_HASH
    assert published.occurred_at == _NOW
    assert published.published_by == _PRINCIPAL_ID


@pytest.mark.unit
def test_decider_rejects_registered_source_status() -> None:
    with pytest.raises(EditionCannotPublishError) as exc:
        decide(
            state=_edition(status=EditionStatus.REGISTERED),
            command=PublishEdition(edition_id=_EDITION_ID),
            context=_context(),
            now=_NOW,
            published_by=_PRINCIPAL_ID,
        )
    assert exc.value.current_status is EditionStatus.REGISTERED


@pytest.mark.unit
def test_decider_rejects_published_source_status() -> None:
    with pytest.raises(EditionCannotPublishError) as exc:
        decide(
            state=_edition(status=EditionStatus.PUBLISHED),
            command=PublishEdition(edition_id=_EDITION_ID),
            context=_context(),
            now=_NOW,
            published_by=_PRINCIPAL_ID,
        )
    assert exc.value.current_status is EditionStatus.PUBLISHED


@pytest.mark.unit
def test_decider_rejects_withdrawn_source_status() -> None:
    with pytest.raises(EditionCannotPublishError) as exc:
        decide(
            state=_edition(status=EditionStatus.WITHDRAWN),
            command=PublishEdition(edition_id=_EDITION_ID),
            context=_context(),
            now=_NOW,
            published_by=_PRINCIPAL_ID,
        )
    assert exc.value.current_status is EditionStatus.WITHDRAWN


@pytest.mark.unit
def test_decider_rejects_sealed_edition_without_content_hash() -> None:
    with pytest.raises(EditionPublishedWithoutContentHashError) as exc:
        decide(
            state=_edition(content_hash=None),
            command=PublishEdition(edition_id=_EDITION_ID),
            context=_context(),
            now=_NOW,
            published_by=_PRINCIPAL_ID,
        )
    assert exc.value.edition_id == _EDITION_ID


@pytest.mark.unit
def test_decider_echoes_handle_scheme_from_context() -> None:
    handle_pid = PersistentIdentifier(
        scheme=PersistentIdentifierScheme.HANDLE,
        value="20.500.0000/cora-stub/abc",
    )
    events = decide(
        state=_edition(),
        command=PublishEdition(edition_id=_EDITION_ID),
        context=_context(external_pid=handle_pid),
        now=_NOW,
        published_by=_PRINCIPAL_ID,
    )
    assert events[0].external_pid_scheme == "Handle"
    assert events[0].external_pid_value == handle_pid.value
