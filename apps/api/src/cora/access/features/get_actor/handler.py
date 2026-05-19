"""Application handler for the `get_actor` query slice.

Cross-BC query-handler shape (Phase 2):

    1. authorize(principal_id, query_name, conduit) -> Allow | Deny
       (under AllowAllAuthorize this is currently a no-op; the call
       site is in place so Phase 3's Trust BC swap is mechanical
       per handler instead of a sweep that risks missing handlers.)
    2. load_<aggregate>(...)        -> Aggregate | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Returns the domain `Actor`, not a DTO. The route layer maps to
`ActorResponse` and the MCP tool maps to its own structured output.
Handlers stay in domain types so non-HTTP/MCP consumers (other BCs,
sagas, projections) get the rich object.
"""

from typing import Protocol
from uuid import UUID

from cora.access.aggregates.actor import Actor, load_actor
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


class Handler(Protocol):
    """Callable interface every get_actor handler implements."""

    async def __call__(
        self,
        query: GetActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Actor | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_actor handler closed over the shared deps."""

    async def handler(
        query: GetActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Actor | None:
        _log.info(
            "get_actor.start",
            query_name=_QUERY_NAME,
            actor_id=str(query.actor_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authorize(
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

        _log.info(
            "get_actor.success",
            query_name=_QUERY_NAME,
            actor_id=str(query.actor_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=actor is not None,
        )
        return actor

    return handler
