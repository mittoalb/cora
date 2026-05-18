"""The `GetCapability` query — intent dataclass for this read slice.

Mirrors `GetFamily` / `GetMethod` / `GetPlan` etc.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetCapability:
    """Read the current state of an existing Capability by id."""

    capability_id: UUID
