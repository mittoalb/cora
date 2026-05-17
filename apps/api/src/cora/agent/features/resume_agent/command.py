"""The `ResumeAgent` command -- intent dataclass for this slice.

Returns a `Suspended` Agent back to `Versioned`. NO `reason`
field: the act of resuming is its own signal; if rationale
matters operators record a Decision separately. Asymmetry with
`SuspendAgent.reason` is deliberate (events carry facts,
Decisions carry rationale).

The resuming actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ResumeAgent:
    """Resume an Agent (`Suspended -> Versioned`)."""

    agent_id: UUID
