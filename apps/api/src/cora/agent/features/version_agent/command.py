"""The `VersionAgent` command -- intent dataclass for this slice.

Promotes a Defined Agent to Versioned (ready-for-invocation;
Anthropic-Skills-style rainbow-deploy ready signal). Source set is
`{Defined}` only; re-versioning a Versioned or Deprecated Agent
raises `AgentCannotVersionError`.

Multi-version-per-kind is NOT achieved by re-versioning the same
id; operators define a new Agent with the same `kind` and a
different `id`. The aggregate's `version` field is captured at
definition time and never mutates.

The promoting actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VersionAgent:
    """Version a Defined Agent (`Defined -> Versioned`)."""

    agent_id: UUID
