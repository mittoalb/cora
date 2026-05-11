"""The `GetPractice` query — intent dataclass for this read slice.

Mirrors `GetMethod` / `GetCapability` / `GetSubject` / `GetActor`:
queries are dataclasses just like commands. They name the read
intent and carry only the input the caller controls; the
application handler adds context (correlation_id, principal_id) at
call time.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetPractice:
    """Read the current state of an existing practice by id."""

    practice_id: UUID
