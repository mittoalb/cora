"""Vertical slice for the `DismissEventInReaction` command.

Operator escape-hatch for a wedged Reaction bookmark: advances the
subscriber past one poison event AND records the dismissal as a
`DecisionRegistered` audit row in the same Postgres transaction.

See [[project-reaction-protocol-design]] (commit 1 of this slice) for
why Reactions are the failure-mode this slice targets. Operationally:
the on-call playbook is "page → dismiss-event with reason → debug
tomorrow" instead of "page → SSH → psql → UPDATE projection_bookmarks."
"""

from cora.agent.features.dismiss_event_in_reaction import tool
from cora.agent.features.dismiss_event_in_reaction.command import (
    DismissEventInReaction,
)
from cora.agent.features.dismiss_event_in_reaction.decider import (
    DismissalContext,
    decide,
)
from cora.agent.features.dismiss_event_in_reaction.handler import Handler, bind
from cora.agent.features.dismiss_event_in_reaction.route import router

__all__ = [
    "DismissEventInReaction",
    "DismissalContext",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
