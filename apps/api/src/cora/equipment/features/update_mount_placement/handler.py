"""Application handler for the `update_mount_placement` slice.

Update-style handler. Delegates to `make_mount_update_handler`
(load Mount stream + authorize + fold + decide + append, with
idempotent no-op on unchanged placement).
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._mount_update_handler import make_mount_update_handler
from cora.equipment.features.update_mount_placement.command import UpdateMountPlacement
from cora.equipment.features.update_mount_placement.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    async def __call__(
        self,
        command: UpdateMountPlacement,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    return make_mount_update_handler(
        deps,
        command_name="UpdateMountPlacement",
        log_prefix="update_mount_placement",
        decide_fn=decide,
    )
