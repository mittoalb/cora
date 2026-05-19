"""Application handler for the `remove_run_from_campaign` slice.

Cross-aggregate update-style handler. Symmetric to add_run_to_campaign:
pre-loads both Campaign and Run streams (with versions), builds a
`CampaignMembershipContext`, calls the pure decider, then writes
BOTH event streams atomically via `EventStore.append_streams`.

204 No Content on success.
"""

from typing import Protocol
from uuid import UUID

from cora.campaign.aggregates.campaign import (
    CampaignNotFoundError,
    event_type_name,
    load_campaign,
    to_payload,
)
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.remove_run_from_campaign.command import RemoveRunFromCampaign
from cora.campaign.features.remove_run_from_campaign.context import CampaignMembershipContext
from cora.campaign.features.remove_run_from_campaign.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import (
    RunNotFoundError,
    load_run,
)
from cora.run.aggregates.run import (
    event_type_name as run_event_type_name,
)
from cora.run.aggregates.run import (
    to_payload as run_to_payload,
)

_CAMPAIGN_STREAM_TYPE = "Campaign"
_RUN_STREAM_TYPE = "Run"
_COMMAND_NAME = "RemoveRunFromCampaign"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every remove_run_from_campaign handler implements."""

    async def __call__(
        self,
        command: RemoveRunFromCampaign,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a remove_run_from_campaign handler closed over the shared deps."""

    async def handler(
        command: RemoveRunFromCampaign,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "remove_run_from_campaign.start",
            command_name=_COMMAND_NAME,
            campaign_id=str(command.campaign_id),
            run_id=str(command.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "remove_run_from_campaign.denied",
                command_name=_COMMAND_NAME,
                campaign_id=str(command.campaign_id),
                run_id=str(command.run_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        campaign = await load_campaign(deps.event_store, command.campaign_id)
        if campaign is None:
            raise CampaignNotFoundError(command.campaign_id)
        _, campaign_version = await deps.event_store.load(
            _CAMPAIGN_STREAM_TYPE, command.campaign_id
        )

        run = await load_run(deps.event_store, command.run_id)
        if run is None:
            raise RunNotFoundError(command.run_id)
        _, run_version = await deps.event_store.load(_RUN_STREAM_TYPE, command.run_id)

        context = CampaignMembershipContext(
            campaign=campaign,
            campaign_version=campaign_version,
            run=run,
            run_version=run_version,
        )

        now = deps.clock.now()

        membership = decide(
            state=campaign,
            command=command,
            context=context,
            now=now,
        )

        campaign_new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in membership.campaign_events
        ]
        run_new_events = [
            to_new_event(
                event_type=run_event_type_name(event),
                payload=run_to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in membership.run_events
        ]

        await deps.event_store.append_streams(
            [
                StreamAppend(
                    stream_type=_CAMPAIGN_STREAM_TYPE,
                    stream_id=command.campaign_id,
                    expected_version=context.campaign_version,
                    events=campaign_new_events,
                ),
                StreamAppend(
                    stream_type=_RUN_STREAM_TYPE,
                    stream_id=command.run_id,
                    expected_version=context.run_version,
                    events=run_new_events,
                ),
            ]
        )

        _log.info(
            "remove_run_from_campaign.success",
            command_name=_COMMAND_NAME,
            campaign_id=str(command.campaign_id),
            run_id=str(command.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            campaign_event_count=len(campaign_new_events),
            run_event_count=len(run_new_events),
        )

    return handler
