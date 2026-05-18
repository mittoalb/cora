"""The `GetClearance` query -- intent dataclass for this read slice.

Mirrors `GetSupply` / `GetFamily` / `GetAsset` / `GetSubject`:
queries are dataclasses just like commands, naming the read intent and
carrying only what the caller controls. The application handler adds
context (correlation_id, principal_id) at call time.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetClearance:
    """Read the current state of an existing clearance by id."""

    clearance_id: UUID
