"""Application handler for the `get_asset` query slice.

Cross-BC query-handler shape (Phase 2b precedent, mirrored from
`get_family` / `get_subject` / `get_actor`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_asset(...)              -> Asset | None  (fold-on-read)
    3. return state                 -> caller maps None to 404 / isError

Returns the domain `Asset`, not a DTO. The route layer maps to
`AssetResponse` and the MCP tool maps to its own structured output.
Handlers stay in domain types so non-HTTP/MCP consumers (other BCs,
sagas, projections) get the rich object.

Query handlers do NOT emit `causation_id` log fields — queries have
no causation chain (they don't emit events that downstream commands
react to). Same convention as `get_family` / `get_subject` /
`get_actor`.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import Asset, load_asset
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.get_asset.query import GetAsset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetAsset"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_asset handler implements."""

    async def __call__(
        self,
        query: GetAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Asset | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_asset handler closed over the shared deps."""

    async def handler(
        query: GetAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Asset | None:
        _log.info(
            "get_asset.start",
            query_name=_QUERY_NAME,
            asset_id=str(query.asset_id),
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
                "get_asset.denied",
                query_name=_QUERY_NAME,
                asset_id=str(query.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        asset = await load_asset(deps.event_store, query.asset_id)

        _log.info(
            "get_asset.success",
            query_name=_QUERY_NAME,
            asset_id=str(query.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=asset is not None,
        )
        return asset

    return handler
