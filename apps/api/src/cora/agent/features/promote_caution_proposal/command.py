"""The `PromoteCautionProposal` command -- intent dataclass for this slice.

Operator-triggered cross-BC promotion of a
`DecisionRegistered(context="CautionProposal")` Decision into a
real Caution write (`register_caution` or `supersede_caution`
depending on the Decision's `choice`).

Input is just the `decision_id`; the promoted Caution's fields
come entirely from the Decision's `inputs.proposed_caution` tuple
written by the CautionDrafter subscriber. Operator edits before
promotion are out-of-scope at v1 (watch item: when frontend ships,
add per-field overrides to this command).

The promoting actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PromoteCautionProposal:
    """Promote a CautionProposal Decision into a real Caution."""

    decision_id: UUID
