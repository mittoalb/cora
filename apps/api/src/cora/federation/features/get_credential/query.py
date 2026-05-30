"""The `GetCredential` query, intent dataclass for this read slice.

Mirrors `GetCalibration` / `GetPermit`: queries are dataclasses just
like commands, naming the read intent and carrying only what the
caller controls. The application handler adds context
(correlation_id, principal_id, surface_id) at call time.

Cross-BC pattern: queries are full vertical slices symmetric with
commands but without a decider (queries don't emit events). The
handler is a thin wrapper around `load_credential` +
`load_credential_timestamps` (Path C composition).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetCredential:
    """Read the current state of an existing Credential by id."""

    credential_id: UUID
