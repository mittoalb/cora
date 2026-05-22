"""Vertical slice for the `RateDecision` command.

Module-as-namespace surface:

    from cora.decision.features import rate_decision

    cmd = rate_decision.RateDecision(
        decision_id=...,
        rating=DecisionRating.USEFUL,
        comment="exactly what I needed",
    )
    handler = rate_decision.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Operator acceptance-signal capture per [[project_run_debrief_design]].
Multiple ratings per (decision, actor) pair are allowed; the
projection (`proj_decision_ratings`) takes latest-per-actor wins.
The audit trail (every rating ever submitted) lives in the event log.
"""

from cora.decision.features.rate_decision import tool
from cora.decision.features.rate_decision.command import RateDecision
from cora.decision.features.rate_decision.decider import decide
from cora.decision.features.rate_decision.handler import Handler, bind
from cora.decision.features.rate_decision.route import router

__all__ = [
    "Handler",
    "RateDecision",
    "bind",
    "decide",
    "router",
    "tool",
]
