"""Application handler for the `install_asset` slice.

Longhand handler. Loads two projection facets BEFORE calling the
pure decider: the Asset's current lifecycle (from asset_summary) and
the Asset's current Mount-installation back-lookup (from
asset_location). Single-stream-write + projection-precondition
pattern (mirrors decommission_mount).
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.mount import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.install_asset.command import InstallAsset
from cora.equipment.features.install_asset.context import InstallAssetContext
from cora.equipment.features.install_asset.decider import decide
from cora.equipment.projections.asset import load_asset_lifecycle
from cora.equipment.projections.asset_location import load_asset_location
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Mount"
_COMMAND_NAME = "InstallAsset"

_log = get_logger(__name__)


class Handler(Protocol):
    async def __call__(
        self,
        command: InstallAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    async def handler(
        command: InstallAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "install_asset.start",
            command_name=_COMMAND_NAME,
            mount_id=str(command.mount_id),
            asset_id=str(command.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "install_asset.denied",
                command_name=_COMMAND_NAME,
                mount_id=str(command.mount_id),
                asset_id=str(command.asset_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        # Load Mount stream + fold.
        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.mount_id,
        )
        history = [from_stored(s) for s in stored]
        state = fold(history)

        # Projection preconditions: (1) Asset's current lifecycle
        # (None when no row), (2) which Mount currently holds this
        # Asset (None when uninstalled). The decider folds both into
        # AssetNotFoundForMountError / AssetNotInstallableError /
        # AssetAlreadyInstalledElsewhereError as appropriate.
        asset_lifecycle = await load_asset_lifecycle(deps.pool, command.asset_id)
        currently_at = await load_asset_location(deps.pool, command.asset_id)
        context = InstallAssetContext(
            asset_lifecycle=asset_lifecycle,
            currently_installed_at_mount_id=currently_at,
        )

        domain_events = decide(
            state=state,
            command=command,
            context=context,
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
            stream_id=command.mount_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "install_asset.success",
            command_name=_COMMAND_NAME,
            mount_id=str(command.mount_id),
            asset_id=str(command.asset_id),
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
