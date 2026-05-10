"""Authorize port: gate every command behind `authorize(principal, command, conduit_id)`.

`principal_id` (not `actor_id`) names the invoker because the Access BC
already owns an `Actor` aggregate; using `actor_id` for both the Actor
aggregate's id and the calling-party's id was a real bug vector at
handler call sites where commands target an Actor aggregate (e.g.
DeactivateActor).

`conduit_id: UUID` (post-3g) names the conduit through which the
command is being invoked. Phase 3e shipped the port with `conduit:
str` and a "default" sentinel — that was a stand-in until the Trust
BC's `Conduit` aggregate (UUID-identified) became real. 3g switched
to `UUID` so the authz layer can route by conduit (3h: TrustAuthorize
now passes the caller's conduit_id to `evaluate`, so policies bound
to one conduit don't gate calls on another).

The default-when-unspecified is the nil UUID
(`UUID(int=0)` = `00000000-...`). Callers that don't yet know their
conduit (most handlers today) pass it; a Policy bound to the nil
conduit_id matches them. As real conduit-routing arrives at the
HTTP / MCP / A2A boundaries, those surfaces will inject their own
conduit_id constants and stop using the nil sentinel.

Phase 1 shipped an `AllowAllAuthorize` stub. Phase 3e shipped the
real `TrustAuthorize` adapter (in `cora.trust.authorize`).
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


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
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id)
        return Allow()
