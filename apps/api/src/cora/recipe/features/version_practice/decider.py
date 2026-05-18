"""Pure decider for the `VersionPractice` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected.

## Deliberate divergence from strict-not-idempotent

Same as version_method (Recipe 6b) and version_family
(Equipment 5f-2): re-versioning with the same tag succeeds and
emits a fresh event. Re-attestation is a legitimate audit moment.
Pinned by `test_decide_allows_versioning_with_same_tag_for_re_attestation`.

Invariants:
  - State must not be None -> PracticeNotFoundError
  - command.version_tag must be 1-50 chars after trimming
    -> InvalidPracticeVersionTagError
  - State.status must be in {Defined, Versioned}
    -> PracticeCannotVersionError(current_status=...)
"""

from datetime import datetime

from cora.recipe.aggregates.practice import (
    PRACTICE_VERSION_TAG_MAX_LENGTH,
    InvalidPracticeVersionTagError,
    Practice,
    PracticeCannotVersionError,
    PracticeNotFoundError,
    PracticeStatus,
    PracticeVersioned,
)
from cora.recipe.features.version_practice.command import VersionPractice

_VERSIONABLE_STATUSES: tuple[PracticeStatus, ...] = (
    PracticeStatus.DEFINED,
    PracticeStatus.VERSIONED,
)


def decide(
    state: Practice | None,
    command: VersionPractice,
    *,
    now: datetime,
) -> list[PracticeVersioned]:
    """Decide the events produced by versioning an existing practice."""
    if state is None:
        raise PracticeNotFoundError(command.practice_id)
    trimmed = command.version_tag.strip()
    if not trimmed or len(trimmed) > PRACTICE_VERSION_TAG_MAX_LENGTH:
        raise InvalidPracticeVersionTagError(command.version_tag)
    if state.status not in _VERSIONABLE_STATUSES:
        raise PracticeCannotVersionError(state.id, current_status=state.status)
    return [
        PracticeVersioned(
            practice_id=state.id,
            version_tag=trimmed,
            occurred_at=now,
        )
    ]
