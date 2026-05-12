"""Vertical slice for the `AppendReasoningEntries` command (8c-b).

Module-as-namespace surface. Mirrors register_decision but takes
the BC-internal `reasoning_store` at bind time (not via Kernel).
"""

from cora.decision.features.append_reasoning_entry import tool
from cora.decision.features.append_reasoning_entry.command import (
    AppendReasoningEntries,
    ReasoningEntryInput,
)
from cora.decision.features.append_reasoning_entry.handler import Handler, bind
from cora.decision.features.append_reasoning_entry.route import router

__all__ = [
    "AppendReasoningEntries",
    "Handler",
    "ReasoningEntryInput",
    "bind",
    "router",
    "tool",
]
