"""The `CheckOutFromVisit` command -- intent dataclass.

Closes the actor's open presence entry. Multi-shift is supported: the
same actor may check in / out repeatedly within a single Visit -- each
cycle produces a separate `PresenceEntry`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CheckOutFromVisit:
    """Close the actor's currently-open presence entry on the Visit."""

    visit_id: UUID
    actor_id: UUID
