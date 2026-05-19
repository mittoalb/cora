"""Authorize port: gate every command behind authorize(principal, command, conduit_id, surface_id).

`principal_id` (not `actor_id`) names the invoker because the Access BC
already owns an `Actor` aggregate; using `actor_id` for both the Actor
aggregate's id and the calling-party's id was a real bug vector at
handler call sites where commands target an Actor aggregate (e.g.
DeactivateActor).

`conduit_id: UUID` (post-3g) names the ISA-99/IEC-62443 inter-zone
channel — comms path between two trust zones — through which the
command would flow. Operationally inert at v1: every handler passes
`UUID(int=0)` nil-sentinel. Reactivation tracked as
project_conduit_injection_design.md WI10.

`surface_id: UUID` (post-Phase-B Iter B) names the process-level
arrival point (HTTP / MCP stdio / MCP streamable-http) through which
the request entered CORA. Closed-StrEnum kind sits on the
`cora.trust.aggregates.surface.Surface` aggregate; surface adapters
in Iter C resolve concrete IDs per request, Phase C layers OAuth
`aud` validation on top.

Defaults: both `conduit_id` and `surface_id` default to nil
`UUID(int=0)` so existing handler call sites work unchanged. As real
routing arrives at the HTTP / MCP / A2A boundaries (Iter C), routes
inject concrete IDs and stop using the nil sentinel — the Phase B
architecture fitness test pins the no-nil-leak invariant.

Phase 1 shipped an `AllowAllAuthorize` stub. Phase 3e shipped the
real `TrustAuthorize` adapter (in `cora.trust.authorize`).
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

_NIL_SENTINEL_ID = UUID(int=0)


@dataclass(frozen=True)
class Allow:
    """Authorization granted."""


@dataclass(frozen=True)
class Deny:
    """Authorization denied with a reason."""

    reason: str


type AuthzResult = Allow | Deny


class Authorize(Protocol):
    """Authorization gate: called before every command."""

    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> AuthzResult: ...


class AllowAllAuthorize:
    """Phase 1 stub: returns Allow for every call.

    Production wiring uses `cora.trust.authorize.TrustAuthorize`;
    AllowAll remains for tests/dev and the documented bootstrap
    workflow (define the gating policy under AllowAll, then restart
    with TrustAuthorize wired against it).
    """

    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = _NIL_SENTINEL_ID,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id, surface_id)
        return Allow()
