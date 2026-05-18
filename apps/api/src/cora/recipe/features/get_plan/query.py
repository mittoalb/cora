"""The `GetPlan` query — intent dataclass for this read slice.

Mirrors `GetPractice` / `GetMethod` / `GetFamily` / `GetSubject`
/ `GetActor`: queries are dataclasses just like commands. They name
the read intent and carry only the input the caller controls; the
application handler adds context (correlation_id, principal_id) at
call time.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetPlan:
    """Read the current state of an existing plan by id."""

    plan_id: UUID
