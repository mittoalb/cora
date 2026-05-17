"""Vertical slice for the `PromoteCautionProposal` command (Phase 8f-c iter 3).

Operator-triggered cross-BC promotion: reads a
`DecisionRegistered(context="CautionProposal")` Decision and writes
either `register_caution` (new Caution) or `supersede_caution`
(refining an existing Active Caution) to the Caution BC.

Per [[project-caution-drafter-design]] Locks > Promotion slice
section.

The promotion verb is the human-in-the-loop curation gate that
makes propose-via-Decision work: CautionDrafter never writes
Cautions directly; an operator explicitly promotes (or implicitly
declines by not promoting). Mirrors ASRS's analyst-curation step.
"""

from cora.agent.features.promote_caution_proposal import tool
from cora.agent.features.promote_caution_proposal.command import PromoteCautionProposal
from cora.agent.features.promote_caution_proposal.handler import Handler, IdempotentHandler, bind
from cora.agent.features.promote_caution_proposal.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "PromoteCautionProposal",
    "bind",
    "router",
    "tool",
]
