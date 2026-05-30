"""Application handler for the `uninstall_asset` slice.

Update-style handler. Delegates to `make_mount_update_handler`
(no projection precondition needed; state-based checks only).
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._mount_update_handler import make_mount_update_handler
from cora.equipment.features.uninstall_asset.command import UninstallAsset
from cora.equipment.features.uninstall_asset.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    async def __call__(
        self,
        command: UninstallAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    return make_mount_update_handler(
        deps,
        command_name="UninstallAsset",
        log_prefix="uninstall_asset",
        decide_fn=decide,
    )
