"""The `VersionMethod` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Versioned. Operators
issue a new version_tag (free text like "v2", "2026-Q3") to mark a
revision of the technique-class definition.

Mirrors `VersionCapability` (Equipment 5f-2) shape and semantics.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VersionMethod:
    """Issue a new version label for an existing method."""

    method_id: UUID
    version_tag: str
