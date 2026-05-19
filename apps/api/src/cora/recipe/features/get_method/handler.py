"""Application handler for the `get_method` query slice.

Cross-BC query-handler shape (Phase 2b precedent, mirrored from
`get_family` / `get_asset` / `get_subject` / `get_actor`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_method(...)             -> Method | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Returns the domain `Method`, not a DTO. The route layer maps to
`MethodResponse` and the MCP tool maps to its own structured
output. Handlers stay in domain types so non-HTTP/MCP consumers
(other BCs, sagas, projections) get the rich object.

Query handlers do NOT emit `causation_id` log fields — queries have
no causation chain (they don't emit events that downstream commands
react to). Same convention as `get_family` / `get_asset`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.method import Method, load_method
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.get_method.query import GetMethod

_QUERY_NAME = "GetMethod"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_method handler implements."""

    async def __call__(
        self,
        query: GetMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> Method | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_method handler closed over the shared deps."""

    async def handler(
        query: GetMethod,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> Method | None:
        _log.info(
            "get_method.start",
            query_name=_QUERY_NAME,
            method_id=str(query.method_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_method.denied",
                query_name=_QUERY_NAME,
                method_id=str(query.method_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        method = await load_method(deps.event_store, query.method_id)

        _log.info(
            "get_method.success",
            query_name=_QUERY_NAME,
            method_id=str(query.method_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=method is not None,
        )
        return method

    return handler
