"""The `DeprecatePractice` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Deprecated. Single-
field command (just practice_id); no body at the API layer. Mirrors
`DeprecateMethod` / `DeprecateCapability`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DeprecatePractice:
    """Mark an existing practice as deprecated."""

    practice_id: UUID
