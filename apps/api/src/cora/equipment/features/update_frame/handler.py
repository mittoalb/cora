"""Application handler for the `update_frame` slice.

Update-style handler. Delegates to `make_frame_update_handler` (load
Frame stream + authorize + fold + decide + append, with idempotent
no-op on unchanged placement).

Not idempotency-wrapped: the no-op-on-unchanged guard at the decider
layer covers the duplicate-submission case.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._frame_update_handler import make_frame_update_handler
from cora.equipment.features.update_frame.command import UpdateFrame
from cora.equipment.features.update_frame.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every update_frame handler implements."""

    async def __call__(
        self,
        command: UpdateFrame,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_frame handler closed over the shared deps."""
    return make_frame_update_handler(
        deps,
        command_name="UpdateFrame",
        log_prefix="update_frame",
        decide_fn=decide,
    )
