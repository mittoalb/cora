"""The `ReleaseControlOfSurface` command -- intent dataclass."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ReleaseControlOfSurface:
    """Requesting Visit releases active control of the named Surface."""

    visit_id: UUID
    surface_id: UUID
