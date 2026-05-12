"""The `GetDecision` query — intent dataclass for this read slice."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetDecision:
    """Read the current state of an existing Decision by id."""

    decision_id: UUID
