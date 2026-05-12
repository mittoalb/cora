"""Vertical slice for the `GetDecision` query."""

from cora.decision.features.get_decision import tool
from cora.decision.features.get_decision.handler import Handler, bind
from cora.decision.features.get_decision.query import GetDecision
from cora.decision.features.get_decision.route import router

__all__ = [
    "GetDecision",
    "Handler",
    "bind",
    "router",
    "tool",
]
