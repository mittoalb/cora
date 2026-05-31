"""Application handler for the `update_frame_placement` slice.

Update-style handler. Delegates to `make_frame_update_handler` (load
Frame stream + authorize + fold + decide + append, with idempotent
no-op on unchanged placement).

Not idempotency-wrapped: the no-op-on-unchanged guard at the decider
layer covers the duplicate-submission case.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._frame_update_handler import make_frame_update_handler
from cora.equipment.features.update_frame_placement.command import UpdateFramePlacement
from cora.equipment.features.update_frame_placement.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every update_frame_placement handler implements."""

    async def __call__(
        self,
        command: UpdateFramePlacement,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_frame_placement handler closed over the shared deps."""
    return make_frame_update_handler(
        deps,
        command_name="UpdateFramePlacement",
        log_prefix="update_frame_placement",
        decide_fn=decide,
    )
