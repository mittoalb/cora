"""The `DeprecateCapability` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Deprecated. Single-
field command (just capability_id); no body at the API layer.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DeprecateCapability:
    """Mark an existing capability as deprecated."""

    capability_id: UUID
