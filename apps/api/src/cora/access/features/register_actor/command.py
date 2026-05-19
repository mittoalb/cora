"""The `RegisterActor` command — intent dataclass for this slice.

Carries only what the caller controls. Server-side concerns
(new aggregate id, wall-clock timestamp, correlation id, command-instance id)
are injected by the handler from infrastructure ports.
"""

from dataclasses import dataclass

from cora.access.aggregates.actor import ActorKind


@dataclass(frozen=True)
class RegisterActor:
    """Register a new actor with the given display name.

    `kind` discriminates `human` (default; UI-driven operator
    registration) from `service_account` (Phase C Iter B-2; machine
    callers — CI bridges, autonomous agent runtime processes, future
    TomoScan/EPICS bridges). `agent`-kind Actors are NOT minted via
    this slice — they go through the cross-BC atomic write in
    `define_agent` per [[project_agent_bc_design]] P0-4.
    """

    name: str
    kind: ActorKind = ActorKind.HUMAN
