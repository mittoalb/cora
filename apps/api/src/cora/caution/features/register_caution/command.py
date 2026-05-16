"""The `RegisterCaution` command -- intent dataclass for this slice.

Carries the caller-controlled fields: the polymorphic `target` (Asset
or Procedure), the classification (`category` + `severity`), the
body (`text` + `workaround`), the operator's actor id, optional `tags`
(empty set allowed), optional `expires_at`, and the hierarchy-
propagation opt-in flag.

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports, matching the cross-BC create-style command
shape locked in Access / Trust / Subject / Equipment / Supply /
Safety.

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
from uuid import UUID

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
    author_actor_id: UUID
    tags: frozenset[str] = field(default_factory=frozenset[str])
    expires_at: datetime | None = None
    propagate_to_children: bool = False
