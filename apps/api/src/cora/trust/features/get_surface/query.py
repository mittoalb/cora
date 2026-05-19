"""The `GetSurface` query — intent dataclass for this read slice."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetSurface:
    """Read the current state of an existing surface by id."""

    surface_id: UUID
