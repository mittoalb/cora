"""Cross-aggregate context the `register_decision` decider validates against.

Built by the `register_decision` handler from `load_actor` +
optional `load_decision` (for parent_id) before reaching the pure
decider. Per gate-review Q2 lock B (existence-only, no status
check), the Actor can be in any lifecycle state including
Deactivated — historical decisions are valid regardless of the
Actor's current status. Same posture for the parent Decision.

Slice-local module by design: only `register_decision` uses it.
Mirrors the `RunStartContext` / `DatasetRegistrationContext`
precedent.
"""

from dataclasses import dataclass

from cora.access.aggregates.actor import Actor
from cora.decision.aggregates.decision import Decision


@dataclass(frozen=True)
class DecisionRegistrationContext:
    """Snapshot of cross-aggregate references at Decision-registration time.

    `actor` is required (always pre-loaded). `parent` is optional
    (None when the command's `parent_id` is None). The decider
    treats both as opaque proof of existence (never inspects
    state).
    """

    actor: Actor
    parent: Decision | None = None
