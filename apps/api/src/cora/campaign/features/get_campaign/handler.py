"""Application handler for the `get_campaign` query slice.

Cross-BC query-handler shape (mirrored from `get_caution` /
`get_supply` / `get_clearance`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_campaign(...)            -> Campaign | None  (fold-on-read)
    3. return state                  -> caller maps None to 404 / isError

Returns the domain `Campaign`, not a DTO. The route layer maps to
`CampaignResponse` and the MCP tool maps to its own structured output.
"""

from typing import Protocol
from uuid import UUID

from cora.campaign.aggregates.campaign import Campaign, load_campaign
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.get_campaign.query import GetCampaign
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_QUERY_NAME = "GetCampaign"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_campaign handler implements."""

    async def __call__(
        self,
        query: GetCampaign,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> Campaign | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_campaign handler closed over the shared deps."""

    async def handler(
        query: GetCampaign,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> Campaign | None:
        _log.info(
            "get_campaign.start",
            query_name=_QUERY_NAME,
            campaign_id=str(query.campaign_id),
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
                "get_campaign.denied",
                query_name=_QUERY_NAME,
                campaign_id=str(query.campaign_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        campaign = await load_campaign(deps.event_store, query.campaign_id)

        _log.info(
            "get_campaign.success",
            query_name=_QUERY_NAME,
            campaign_id=str(query.campaign_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=campaign is not None,
        )
        return campaign

    return handler
