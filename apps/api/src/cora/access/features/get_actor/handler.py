"""Application handler for the `get_actor` query slice.

Cross-BC query-handler shape:

    1. authorize(principal_id, query_name, conduit) -> Allow | Deny
       (under AllowAllAuthorize this is currently a no-op; the call
       site is in place so a future Trust BC swap is mechanical
       per handler instead of a sweep that risks missing handlers.)
    2. load_<aggregate>(...)        -> Aggregate | None  (fold-on-read)
    3. resolve display_name via load_actor_display_name (PII vault)
    4. return ActorView             -> caller maps None to 404 / isError

Returns `ActorView | None`: the Actor aggregate state (id, kind,
is_active) plus the display name composed from the BC-internal PII
vault (`actor_profile`). Per the PII vault pattern, the event log
carries no PII; the display name lives in the mutable side table and
is resolved at read time. Post-erasure the actor_id reference stays
valid and the helper returns `DELETED_ACTOR_DISPLAY_NAME`.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.access.aggregates.actor import (
    Actor,
    ProfileStore,
    load_actor,
    load_actor_display_name,
)
from cora.access.errors import UnauthorizedError
from cora.access.features.get_actor.query import GetActor
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetActor"

# structlog loggers are lazy: get_logger() returns a proxy and config is
# applied at first .info() call. Module-level binding is safe even though
# configure_logging() runs later in build_kernel().
_log = get_logger(__name__)


@dataclass(frozen=True)
class ActorView:
    """Read-side composition of Actor aggregate + display name from
    the PII vault.

    The aggregate carries no PII; the display name comes from the
    `actor_profile` table via `load_actor_display_name`, which
    returns the tombstone literal for absent (erased or
    never-registered) rows. Route + MCP-tool layers destructure
    this into their wire DTOs.
    """

    actor: Actor
    display_name: str


class Handler(Protocol):
    """Callable interface every get_actor handler implements."""

    async def __call__(
        self,
        query: GetActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ActorView | None: ...


def bind(deps: Kernel, *, profile_store: ProfileStore) -> Handler:
    """Build a get_actor handler closed over the shared deps + PII vault."""

    async def handler(
        query: GetActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ActorView | None:
        _log.info(
            "get_actor.start",
            query_name=_QUERY_NAME,
            actor_id=str(query.actor_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_actor.denied",
                query_name=_QUERY_NAME,
                actor_id=str(query.actor_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        actor = await load_actor(deps.event_store, query.actor_id)
        if actor is None:
            _log.info(
                "get_actor.success",
                query_name=_QUERY_NAME,
                actor_id=str(query.actor_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None
        display_name = await load_actor_display_name(profile_store, actor.id)

        _log.info(
            "get_actor.success",
            query_name=_QUERY_NAME,
            actor_id=str(query.actor_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
        )
        return ActorView(actor=actor, display_name=display_name)

    return handler


__all__ = [
    "ActorView",
    "Handler",
    "bind",
]
