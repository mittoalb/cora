"""Unit tests for the `version_practice` slice's pure decider.

Mirror of `test_version_method_decider.py` and
`test_version_capability_decider.py`. Multi-source guard
`Defined | Versioned -> Versioned`; only Deprecated rejected.
Same deliberate divergence from strict-not-idempotent.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.practice import (
    InvalidPracticeVersionTagError,
    Practice,
    PracticeCannotVersionError,
    PracticeName,
    PracticeNotFoundError,
    PracticeStatus,
    PracticeVersioned,
)
from cora.recipe.features import version_practice
from cora.recipe.features.version_practice import VersionPractice

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _practice(
    *,
    status: PracticeStatus = PracticeStatus.DEFINED,
    current_version: str | None = None,
) -> Practice:
    return Practice(
        id=uuid4(),
        name=PracticeName("APS Standard Tomography"),
        method_id=uuid4(),
        site_id=uuid4(),
        status=status,
        current_version=current_version,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [PracticeStatus.DEFINED, PracticeStatus.VERSIONED],
)
def test_decide_emits_practice_versioned_for_each_allowed_source_status(
    source: PracticeStatus,
) -> None:
    state = _practice(status=source)
    events = version_practice.decide(
        state=state,
        command=VersionPractice(practice_id=state.id, version_tag="v2"),
        now=_NOW,
    )
    assert events == [PracticeVersioned(practice_id=state.id, version_tag="v2", occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_trims_version_tag_via_decider() -> None:
    state = _practice()
    events = version_practice.decide(
        state=state,
        command=VersionPractice(practice_id=state.id, version_tag="  v2  "),
        now=_NOW,
    )
    assert events[0].version_tag == "v2"


@pytest.mark.unit
def test_decide_raises_practice_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(PracticeNotFoundError) as exc_info:
        version_practice.decide(
            state=None,
            command=VersionPractice(practice_id=target_id, version_tag="v2"),
            now=_NOW,
        )
    assert exc_info.value.practice_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_empty_string() -> None:
    state = _practice()
    with pytest.raises(InvalidPracticeVersionTagError):
        version_practice.decide(
            state=state,
            command=VersionPractice(practice_id=state.id, version_tag=""),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_whitespace_only() -> None:
    state = _practice()
    with pytest.raises(InvalidPracticeVersionTagError):
        version_practice.decide(
            state=state,
            command=VersionPractice(practice_id=state.id, version_tag="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_too_long() -> None:
    state = _practice()
    with pytest.raises(InvalidPracticeVersionTagError):
        version_practice.decide(
            state=state,
            command=VersionPractice(practice_id=state.id, version_tag="v" * 51),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_cannot_version_for_deprecated_status() -> None:
    state = _practice(status=PracticeStatus.DEPRECATED, current_version="v1")
    with pytest.raises(PracticeCannotVersionError) as exc_info:
        version_practice.decide(
            state=state,
            command=VersionPractice(practice_id=state.id, version_tag="v2"),
            now=_NOW,
        )
    assert exc_info.value.practice_id == state.id
    assert exc_info.value.current_status is PracticeStatus.DEPRECATED


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_statuses() -> None:
    state = _practice(status=PracticeStatus.DEPRECATED)
    with pytest.raises(PracticeCannotVersionError) as exc_info:
        version_practice.decide(
            state=state,
            command=VersionPractice(practice_id=state.id, version_tag="v2"),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Deprecated" in msg
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _practice()
    command = VersionPractice(practice_id=state.id, version_tag="v2")
    first = version_practice.decide(state=state, command=command, now=_NOW)
    second = version_practice.decide(state=state, command=command, now=_NOW)
    assert first == second


@pytest.mark.unit
def test_decide_allows_versioning_with_same_tag_for_re_attestation() -> None:
    """Mirrors the deliberate divergence pinned for version_method
    (Recipe 6b) and version_capability (Equipment 5f-2)."""
    state = _practice(status=PracticeStatus.VERSIONED, current_version="v2")
    events = version_practice.decide(
        state=state,
        command=VersionPractice(practice_id=state.id, version_tag="v2"),
        now=_NOW,
    )
    assert events == [PracticeVersioned(practice_id=state.id, version_tag="v2", occurred_at=_NOW)]
