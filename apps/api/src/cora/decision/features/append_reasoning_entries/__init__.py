"""Vertical slice for the `AppendReasoningEntries` command.

Module-as-namespace surface. Mirrors register_decision but takes
the BC-internal `reasoning_store` at bind time (not via Kernel).
"""

from cora.decision.features.append_reasoning_entries import tool
from cora.decision.features.append_reasoning_entries.command import (
    AppendReasoningEntries,
    ReasoningEntryInput,
)
from cora.decision.features.append_reasoning_entries.handler import Handler, bind
from cora.decision.features.append_reasoning_entries.route import router

__all__ = [
    "AppendReasoningEntries",
    "Handler",
    "ReasoningEntryInput",
    "bind",
    "router",
    "tool",
]
