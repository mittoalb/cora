"""The `GrantToolToAgent` command -- intent dataclass for this slice.

Adds one MCP `tool_name` to the Agent's per-agent allowlist.
Idempotent: granting a tool the Agent already has emits NO event.

The granting actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GrantToolToAgent:
    """Grant one MCP tool to an Agent."""

    agent_id: UUID
    tool_name: str
