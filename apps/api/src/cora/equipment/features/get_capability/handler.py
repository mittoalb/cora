"""Application handler for the `get_capability` query slice.

Cross-BC query-handler shape (Phase 2b precedent, mirrored from
`get_actor` / `get_subject`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_capability(...)         -> Capability | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Returns the domain `Capability`, not a DTO. The route layer maps
to `CapabilityResponse` and the MCP tool maps to its own
structured output. Handlers stay in domain types so non-HTTP/MCP
consumers (other BCs, sagas, projections) get the rich object.

Query handlers do NOT emit `causation_id` log fields — queries
have no causation chain (they don't emit events that downstream
commands react to). Same convention as `get_actor` / `get_subject`.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.capability import Capability, load_capability
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.get_capability.query import GetCapability
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_QUERY_NAME = "GetCapability"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_capability handler implements."""

    async def __call__(
        self,
        query: GetCapability,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Capability | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_capability handler closed over the shared deps."""

    async def handler(
        query: GetCapability,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> Capability | None:
        _log.info(
            "get_capability.start",
            query_name=_QUERY_NAME,
            capability_id=str(query.capability_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_capability.denied",
                query_name=_QUERY_NAME,
                capability_id=str(query.capability_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        capability = await load_capability(deps.event_store, query.capability_id)

        _log.info(
            "get_capability.success",
            query_name=_QUERY_NAME,
            capability_id=str(query.capability_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=capability is not None,
        )
        return capability

    return handler
