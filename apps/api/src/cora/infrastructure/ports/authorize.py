"""Authorize port: gate every command behind authz.authorize(principal, command, conduit, surface).

`principal_id` (not `actor_id`) names the invoker because the Access BC
already owns an `Actor` aggregate; using `actor_id` for both the Actor
aggregate's id and the calling-party's id was a real bug vector at
handler call sites where commands target an Actor aggregate (for example,
DeactivateActor).

`conduit_id: UUID` names the ISA-99/IEC-62443 inter-zone
channel — comms path between two trust zones — through which the
command would flow. Operationally inert at v1: every handler passes
`UUID(int=0)` nil-sentinel. Reactivation tracked as
project_conduit_injection_design.md WI10.

`surface_id: UUID` names the process-level arrival point (HTTP /
MCP stdio / MCP streamable-http) through which the request entered
CORA. Closed-StrEnum kind sits on the
`cora.trust.aggregates.surface.Surface` aggregate; surface adapters
resolve concrete IDs per request, and edge-auth layers OAuth `aud`
validation on top.

Defaults: both `conduit_id` and `surface_id` default to nil
`UUID(int=0)` so existing handler call sites work unchanged. As real
routing arrives at the HTTP / MCP / A2A boundaries, routes inject
concrete IDs and stop using the nil sentinel — the architecture
fitness test pins the no-nil-leak invariant.

`AllowAllAuthorize` is the no-op stub used for dev/test and the
documented bootstrap workflow; `TrustAuthorize`
(in `cora.trust.authorize`) is the production adapter.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class Allow:
    """Authorization granted."""


@dataclass(frozen=True)
class Deny:
    """Authorization denied with a reason."""

    reason: str


type AuthzResult = Allow | Deny


class Authorize(Protocol):
    """Authorization gate: called before every command.

    Named-method (not `__call__`) per Python typing-community guidance
    (PEP 544 + typing spec + mypy docs): `__call__` Protocols are for
    callback signatures `Callable[...]` can't express (variadic,
    overloaded, complex generic). A single-operation domain port uses
    a regular method, matching CORA's other ports (`Clock.now`,
    `EventStore.load`, `TokenVerifier.verify`, …) and the broader
    authorization-library corpus (Spring Security 6's
    `AuthorizationManager.authorize`, Pundit's `authorize`, Cedar's
    `is_authorized`, Casbin's `enforce`).

    The seam: `Kernel.authz: Authorize` with call sites reading
    `await deps.authz.authorize(...)` — "use the authz port to
    authorize this command." Factory protocols (`AuthorizeFactory`,
    `LLMFactory`) DO use `__call__` because they ARE construction
    functions; this port is not.
    """

    async def authorize(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AuthzResult: ...


class AllowAllAuthorize:
    """No-op stub: returns Allow for every call.

    Production wiring uses `cora.trust.authorize.TrustAuthorize`;
    AllowAll remains for tests/dev and the documented bootstrap
    workflow (define the gating policy under AllowAll, then restart
    with TrustAuthorize wired against it).
    """

    async def authorize(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id, surface_id)
        return Allow()
