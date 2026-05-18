"""The `VersionPlan` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Versioned. Operators
issue a new version_tag to mark a revision of the Plan binding (for
example: "added an extra detector", "changed sample stage assembly").

Mirrors `VersionPractice` (Recipe 6d-2) / `VersionMethod` (Recipe 6b)
/ `VersionFamily` (Equipment 5f-2) shape and semantics.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VersionPlan:
    """Issue a new version label for an existing plan."""

    plan_id: UUID
    version_tag: str
