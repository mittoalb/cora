"""Vertical slice for the `AppendInferences` command.

Module-as-namespace surface. Mirrors register_decision but takes
the BC-internal `inference_store` at bind time (not via Kernel).
"""

from cora.decision.features.append_inferences import tool
from cora.decision.features.append_inferences.command import (
    AppendInferences,
    ReasoningEntryInput,
)
from cora.decision.features.append_inferences.handler import Handler, bind
from cora.decision.features.append_inferences.route import router

__all__ = [
    "AppendInferences",
    "Handler",
    "ReasoningEntryInput",
    "bind",
    "router",
    "tool",
]
