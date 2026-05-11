"""The `GetRun` query — intent dataclass for this read slice.

Mirrors `GetPlan` / `GetPractice` / `GetMethod` / `GetCapability`
/ `GetSubject` / `GetActor`: queries are dataclasses just like
commands.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetRun:
    """Read the current state of an existing run by id."""

    run_id: UUID
