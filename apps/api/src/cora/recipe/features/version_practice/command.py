"""The `VersionPractice` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Versioned. Operators
issue a new version_tag to mark a revision of the facility-adapted
recipe (for example: "added safety hold-point after sample exchange",
"new default dwell time").

Mirrors `VersionMethod` (Recipe 6b) and `VersionFamily`
(Equipment 5f-2) shape and semantics.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VersionPractice:
    """Issue a new version label for an existing practice."""

    practice_id: UUID
    version_tag: str
