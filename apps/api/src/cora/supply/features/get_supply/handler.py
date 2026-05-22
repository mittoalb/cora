"""Application handler for the `get_supply` query slice.

Cross-BC query-handler shape, mirrored from
`get_actor` / `get_subject` / `get_family`:

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_supply(...)             -> Supply | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Returns the domain `Supply`, not a DTO. The route layer maps to
`SupplyResponse` and the MCP tool maps to its own structured output.
Handlers stay in domain types so non-HTTP/MCP consumers (other BCs,
sagas, projections) get the rich object.

Query handlers do NOT emit `causation_id` log fields — queries have
no causation chain (they don't emit events that downstream commands
react to). Same convention as `get_family` / `get_subject`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.supply.aggregates.supply import Supply, load_supply
from cora.supply.errors import UnauthorizedError
from cora.supply.features.get_supply.query import GetSupply

_QUERY_NAME = "GetSupply"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_supply handler implements."""

    async def __call__(
        self,
        query: GetSupply,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Supply | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_supply handler closed over the shared deps."""

    async def handler(
        query: GetSupply,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Supply | None:
        _log.info(
            "get_supply.start",
            query_name=_QUERY_NAME,
            supply_id=str(query.supply_id),
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
                "get_supply.denied",
                query_name=_QUERY_NAME,
                supply_id=str(query.supply_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        supply = await load_supply(deps.event_store, query.supply_id)

        _log.info(
            "get_supply.success",
            query_name=_QUERY_NAME,
            supply_id=str(query.supply_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=supply is not None,
        )
        return supply

    return handler
