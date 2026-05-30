"""The `DecommissionMount` command - intent dataclass."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DecommissionMount:
    """Decommission an existing mount (terminal lifecycle)."""

    mount_id: UUID
    reason: str
