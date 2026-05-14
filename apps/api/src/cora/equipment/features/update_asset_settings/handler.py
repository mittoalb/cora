"""Application handler for the `update_asset_settings` slice.

Update-style handler — load + fold + decide + append. NOT
idempotency-wrapped (no-op-on-unchanged at the decider; HTTP-layer
caching adds no value).

**Stays longhand (does NOT use make_asset_update_handler).** This
slice is the first that needs to load MORE than just the target
Asset stream: to validate against the union of the Asset's
currently-assigned Capabilities' settings_schemas (5g-a), the
handler must also load each Capability stream concurrently. The
factory's load+decide loop only knows how to read one stream;
threading a "related-streams loader" hook through the factory for
this one slice would cost more LOC than the inlined ~150 lines
saves, so this slice keeps the longhand body.

The `key_count` log field at start/success is the only externally-
visible diagnostic for the patch shape; the patch itself is captured
on the emitted event payload (post-merge, full dict) and is the
source of truth for audit.
"""

import asyncio
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    AssetEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.capability.read import load_capability
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.update_asset_settings.command import UpdateAssetSettings
from cora.equipment.features.update_asset_settings.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

if TYPE_CHECKING:
    from cora.equipment.aggregates.capability.state import Capability

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "UpdateAssetSettings"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every update_asset_settings handler implements."""

    async def __call__(
        self,
        command: UpdateAssetSettings,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_asset_settings handler closed over the shared deps."""

    async def handler(
        command: UpdateAssetSettings,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "update_asset_settings.start",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            key_count=len(command.settings_patch),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "update_asset_settings.denied",
                command_name=_COMMAND_NAME,
                asset_id=str(command.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
        )
        history: list[AssetEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        # Concurrently load every assigned Capability's stream so we
        # can union their schemas. If the Asset doesn't exist yet
        # (state is None), capabilities is empty — the decider will
        # raise AssetNotFoundError anyway.
        capability_ids = list(state.capabilities) if state is not None else []
        loaded: list[Capability | None] = await asyncio.gather(
            *[load_capability(deps.event_store, cid) for cid in capability_ids],
        )
        # Drop any None results (Capability stream missing — ID
        # references a non-existent stream). Eventual-consistency
        # stance: an Asset can hold a capability_id that no longer
        # corresponds to a real Capability; we treat such refs as
        # schemaless rather than raising. The decider's validator
        # will tolerate unknown keys in this case (matches schemaless-
        # Capability semantics).
        capabilities = [c for c in loaded if c is not None]

        domain_events = decide(
            state=state,
            command=command,
            capabilities=capabilities,
            now=now,
        )

        new_events = [
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
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "update_asset_settings.success",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            key_count=len(command.settings_patch),
            capability_count=len(capabilities),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
