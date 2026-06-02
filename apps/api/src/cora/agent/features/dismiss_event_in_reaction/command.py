"""Operator command to dismiss a poison event from a Reaction's bookmark.

Operator-invoked recovery action: when a Reaction (e.g.,
`RunDebriefer`, `CautionDrafter`) wedges on a single event the
subscriber's `apply()` cannot process (poison event, schema drift,
unrecoverable LLM failure), the operator hits this slice to:

  1. Advance the subscriber's `projection_bookmarks` row past the
     event, and
  2. Record the dismissal as an auditable `DecisionRegistered`
     (`context = "ReactionDismissal"`, `choice = "EventDismissed"`)
     so the operator action is preserved in the same audit log as
     every other operator judgment call.

Both writes happen atomically inside a single Postgres transaction
(mirrors the `forget_actor` cross-store pattern).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DismissEventInReaction:
    """Advance `subscriber_name`'s bookmark past `event_id`; record a
    Decision under operator identity.

    Fields:
      - `subscriber_name`: the bookmark `name` (matches the Reaction
        / Subscriber's `name` attribute). The slice queries
        `projection_bookmarks WHERE name = subscriber_name`.
      - `event_id`: the event the operator wants to dismiss. The slice
        looks it up in the `events` table to resolve its
        (transaction_id, position) cursor before advancing.
      - `reason`: free-form text the operator supplies explaining the
        dismissal. Carried verbatim into `DecisionRegistered.reasoning`
        for audit; trimmed to the Decision aggregate's choice-length
        bound.
    """

    subscriber_name: str
    event_id: UUID
    reason: str
