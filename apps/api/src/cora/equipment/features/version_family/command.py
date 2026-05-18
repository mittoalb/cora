"""The `VersionFamily` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Versioned. Operators
issue a new version_tag (free text like "v2", "2026-Q3") to mark a
revision of the technique-class definition.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VersionFamily:
    """Issue a new version label for an existing capability."""

    family_id: UUID
    version_tag: str
