"""The `RegisterCaution` command -- intent dataclass for this slice.

Carries the caller-controlled fields: the polymorphic `target` (Asset
or Procedure), the classification (`category` + `severity`), the
body (`text` + `workaround`), optional `tags` (empty set allowed),
optional `expires_at`, and the hierarchy-propagation opt-in flag.

`author_actor_id` is intentionally NOT on the command: the handler
derives it from the authenticated `principal_id` envelope and passes
it as a keyword-only argument to the decider. The design memo says
"at register time they are equal"; enforcing that by construction
removes the API-surface route for a caller to spoof authorship by
supplying any UUID.

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids, author_actor_id) are injected by the
handler from infrastructure ports / the request envelope, matching
the cross-BC create-style command shape locked in Access / Trust /
Subject / Equipment / Supply / Safety.

`target` is typed as `CautionTarget` (the day-1 discriminated union
of `AssetTarget` + `ProcedureTarget`) so callers cannot pass an
invalid value; the route's Pydantic body + the MCP tool's argument
schema both enforce this at the API boundary via the shared
`TargetDTO` in `cora.caution._caution_dtos`.

`workaround` is REQUIRED (corpus's strongest convergence). The
decider enforces the bounded-text constraint via `CautionWorkaround`;
the API boundary additionally enforces `min_length=1, max_length=2000`.

`expires_at` is operator-supplied (optional); the decider rejects
past-dated values relative to `now` (`InvalidCautionExpiresAtError`).
Per the non-determinism principle, the comparison clock is the
handler-injected `now`, not `datetime.now()`.
"""

from dataclasses import dataclass, field
from datetime import datetime

from cora.caution.aggregates.caution import (
    CautionCategory,
    CautionSeverity,
    CautionTarget,
)


@dataclass(frozen=True)
class RegisterCaution:
    """Register a new caution (lands in Active)."""

    target: CautionTarget
    category: CautionCategory
    severity: CautionSeverity
    text: str
    workaround: str
    tags: frozenset[str] = field(default_factory=frozenset[str])
    expires_at: datetime | None = None
    propagate_to_children: bool = False
