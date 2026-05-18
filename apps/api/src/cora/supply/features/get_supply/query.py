"""The `GetSupply` query — intent dataclass for this read slice.

Mirrors `GetFamily` / `GetAsset` / `GetSubject`: queries are
dataclasses just like commands, naming the read intent and carrying
only what the caller controls. The application handler adds context
(correlation_id, principal_id) at call time.

Cross-BC pattern: queries are full vertical slices symmetric with
commands but without a decider (queries don't emit events). The
handler is essentially a thin wrapper around the aggregate's read
repository (`load_supply`).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetSupply:
    """Read the current state of an existing supply by id."""

    supply_id: UUID
