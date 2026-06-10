"""The `DeprecateClearanceTemplate` command -- intent dataclass for this slice."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DeprecateClearanceTemplate:
    """Deprecate an Active clearance template (`Active -> Deprecated`)."""

    template_id: UUID


__all__ = ["DeprecateClearanceTemplate"]
