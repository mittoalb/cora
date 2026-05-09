"""Application handler for the `get_actor` query slice.

Cross-BC query-handler shape (Phase 2):

    1. clock.now()                  -> domain timestamp (for log only)
    2. load_<aggregate>(...)        -> Actor | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Queries do not (yet) call `authorize`. Phase 3 with the Trust BC will
add query authorization with a proper port shape (likely an
`Authorize.read(...)` overload or a renamed `command_name` -> `operation_name`
parameter). For Phase 2 the principal_id is logged for observability
and accepted in the handler signature for future-proofing — the kwarg
list won't change when authorization lands.

Returns the domain `Actor`, not a DTO. The route layer maps to
`ActorResponse` and the MCP tool maps to its own structured output.
Handlers stay in domain types so non-HTTP/MCP consumers (other BCs,
sagas, projections) get the rich object.
"""

from typing import Protocol
from uuid import UUID

from cora.access.aggregates.actor import Actor, load_actor
from cora.access.features.get_actor.query import GetActor
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.logging import get_logger

_QUERY_NAME = "GetActor"

# structlog loggers are lazy: get_logger() returns a proxy and config is
# applied at first .info() call. Module-level binding is safe even though
# configure_logging() runs later in build_shared_deps().
_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_actor handler implements."""

    async def __call__(
        self,
        query: GetActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Actor | None: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a get_actor handler closed over the shared deps."""

    async def handler(
        query: GetActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Actor | None:
        _log.info(
            "get_actor.start",
            query_name=_QUERY_NAME,
            target_actor_id=str(query.actor_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )
        actor = await load_actor(deps.event_store, query.actor_id)
        _log.info(
            "get_actor.success",
            query_name=_QUERY_NAME,
            target_actor_id=str(query.actor_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=actor is not None,
        )
        return actor

    return handler
