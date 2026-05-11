"""The `GetCapability` query — intent dataclass for this read slice.

Queries are dataclasses just like commands. Mirrors `GetSubject` /
`GetActor`: they name the read intent and carry only the input the
caller controls; the application handler adds context
(correlation_id, principal_id) at call time.

Cross-BC pattern: queries are full vertical slices symmetric with
commands but without a decider (queries don't emit events). The
handler is essentially a thin wrapper around the aggregate's read
repository (`load_capability`).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetCapability:
    """Read the current state of an existing capability by id."""

    capability_id: UUID
