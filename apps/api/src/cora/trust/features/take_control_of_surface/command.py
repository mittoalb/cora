"""The `TakeControlOfSurface` command -- intent dataclass."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TakeControlOfSurface:
    """Requesting Visit takes active control of the named Surface."""

    visit_id: UUID
    surface_id: UUID
