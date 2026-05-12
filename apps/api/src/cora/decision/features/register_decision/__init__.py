"""Vertical slice for the `RegisterDecision` command."""

from cora.decision.features.register_decision import tool
from cora.decision.features.register_decision.command import RegisterDecision
from cora.decision.features.register_decision.context import DecisionRegistrationContext
from cora.decision.features.register_decision.decider import decide
from cora.decision.features.register_decision.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.decision.features.register_decision.route import router

__all__ = [
    "DecisionRegistrationContext",
    "Handler",
    "IdempotentHandler",
    "RegisterDecision",
    "bind",
    "decide",
    "router",
    "tool",
]
