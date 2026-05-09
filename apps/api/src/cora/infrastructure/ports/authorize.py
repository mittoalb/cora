"""Authorize port: gate every command behind `authorize(actor, command, conduit)`.

Phase 1 ships an `AllowAllAuthorize` stub. The real implementation arrives
in Phase 3 with the Trust BC, where Zone/Conduit/Policy aggregates resolve
the authorization. The port shape stays identical; only the adapter changes.
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
        actor_id: UUID,
        command_name: str,
        conduit: str,
    ) -> AuthzResult: ...


class AllowAllAuthorize:
    """Phase 1 stub: returns Allow for every call.

    Replaced in Phase 3 by an adapter that consults `Trust.Policy`.
    """

    async def __call__(
        self,
        actor_id: UUID,
        command_name: str,
        conduit: str,
    ) -> AuthzResult:
        return Allow()
