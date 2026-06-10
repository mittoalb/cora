"""Property-based tests for `publish_edition.decide`.

Universal claims across generated inputs:

  - state.status != SEALED always raises EditionCannotPublishError.
  - a Sealed state whose content_hash is None always raises
    EditionPublishedWithoutContentHashError.
  - any valid Sealed Edition + any minted PID + any published_content_hash
    produces a single EditionPublished echoing the context's external_pid
    (scheme + value) and published_content_hash, regardless of the rest
    of the state's shape.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

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

if TYPE_CHECKING:
    from uuid import UUID

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_SEAL_HASH = "f" * 64
_NON_SEALED_STATUS = st.sampled_from([s for s in EditionStatus if s is not EditionStatus.SEALED])
_PID_VALUE = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=120,
)
_HASH = st.text(
    alphabet="0123456789abcdef",
    min_size=64,
    max_size=64,
)


def _edition(
    edition_id: UUID,
    *,
    status: EditionStatus = EditionStatus.SEALED,
    content_hash: str | None = _SEAL_HASH,
) -> Edition:
    return Edition(
        id=edition_id,
        kind=EditionKind.ROCRATE,
        title=EditionTitle("E"),
        dataset_ids=frozenset({edition_id}),
        creators=(Creator(actor_id=ActorId(edition_id)),),
        registered_at=_NOW,
        registered_by=ActorId(edition_id),
        status=status,
        publisher_facility_code=FacilityCode("cora"),
        publication_year=2026,
        content_hash=content_hash,
        sealed_at=_NOW,
        sealed_by=ActorId(edition_id),
    )


@pytest.mark.unit
@given(edition_id=st.uuids(), status=_NON_SEALED_STATUS)
def test_decider_rejects_non_sealed_status_for_any_input(
    edition_id: UUID,
    status: EditionStatus,
) -> None:
    state = _edition(edition_id, status=status)
    ctx = PublishEditionContext(
        external_pid=PersistentIdentifier(scheme=PersistentIdentifierScheme.DOI, value="10.0/x"),
        published_content_hash=_SEAL_HASH,
    )
    with pytest.raises(EditionCannotPublishError):
        decide(
            state=state,
            command=PublishEdition(edition_id=edition_id),
            context=ctx,
            now=_NOW,
            published_by=ActorId(edition_id),
        )


@pytest.mark.unit
@given(edition_id=st.uuids())
def test_decider_rejects_sealed_without_content_hash(edition_id: UUID) -> None:
    state = _edition(edition_id, content_hash=None)
    ctx = PublishEditionContext(
        external_pid=PersistentIdentifier(scheme=PersistentIdentifierScheme.DOI, value="10.0/x"),
        published_content_hash=_SEAL_HASH,
    )
    with pytest.raises(EditionPublishedWithoutContentHashError):
        decide(
            state=state,
            command=PublishEdition(edition_id=edition_id),
            context=ctx,
            now=_NOW,
            published_by=ActorId(edition_id),
        )


@pytest.mark.unit
@given(
    edition_id=st.uuids(),
    scheme=st.sampled_from(list(PersistentIdentifierScheme)),
    pid_value=_PID_VALUE,
    published_content_hash=_HASH,
)
def test_decider_happy_path_emits_one_edition_published(
    edition_id: UUID,
    scheme: PersistentIdentifierScheme,
    pid_value: str,
    published_content_hash: str,
) -> None:
    state = _edition(edition_id)
    minted = PersistentIdentifier(scheme=scheme, value=pid_value)
    ctx = PublishEditionContext(
        external_pid=minted,
        published_content_hash=published_content_hash,
    )
    events = decide(
        state=state,
        command=PublishEdition(edition_id=edition_id),
        context=ctx,
        now=_NOW,
        published_by=ActorId(edition_id),
    )
    assert len(events) == 1
    published = events[0]
    assert isinstance(published, EditionPublished)
    assert published.edition_id == edition_id
    assert published.external_pid_scheme == scheme.value
    assert published.external_pid_value == minted.value
    assert published.published_content_hash == published_content_hash
