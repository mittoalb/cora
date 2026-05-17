"""The `GetAgent` query -- intent dataclass for this read slice.

Mirrors `GetCaution` / `GetSupply` / `GetClearance`: queries are
dataclasses just like commands, naming the read intent and carrying
only what the caller controls. The application handler adds context
(correlation_id, principal_id) at call time.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetAgent:
    """Read the current state of an existing Agent by id."""

    agent_id: UUID
