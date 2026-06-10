"""The `ActivateClearanceTemplate` command -- intent dataclass for this slice."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ActivateClearanceTemplate:
    """Activate a Draft clearance template (`Draft -> Active`)."""

    template_id: UUID


__all__ = ["ActivateClearanceTemplate"]
