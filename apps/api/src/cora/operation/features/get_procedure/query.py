"""The `GetProcedure` query -- intent dataclass for this read slice.

Mirrors `GetSupply` / `GetFamily` / `GetAsset` / `GetSubject`:
queries are dataclasses just like commands, naming the read intent
and carrying only what the caller controls. The application handler
adds context (correlation_id, principal_id) at call time.

Cross-BC pattern: queries are full vertical slices symmetric with
commands but without a decider (queries don't emit events). The
handler is essentially a thin wrapper around the aggregate's read
repository (`load_procedure`).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetProcedure:
    """Read the current state of an existing procedure by id."""

    procedure_id: UUID
