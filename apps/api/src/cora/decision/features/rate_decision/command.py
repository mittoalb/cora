"""The `RateDecision` command -- intent dataclass for this slice.

Carries the caller-controlled fields: the target `decision_id`, the
closed `rating` value (useful / misleading / ignored), and an
optional free-form `comment`.

`rated_by` is intentionally NOT on the command: the handler
derives it from the authenticated `principal_id` envelope and passes
it as a keyword-only argument to the decider. Same author-spoofing-
closed convention as `register_caution.author_actor_id` (11b-a
gate-review cleanup N9). Operators rate Decisions self-recorded.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.decision.aggregates.decision import DecisionRating


@dataclass(frozen=True)
class RateDecision:
    """Rate an existing Decision (operator acceptance signal)."""

    decision_id: UUID
    rating: DecisionRating
    comment: str | None = None
