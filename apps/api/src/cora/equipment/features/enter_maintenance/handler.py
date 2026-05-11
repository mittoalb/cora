"""Application handler for the `enter_maintenance` slice.

Update-style handler. The full canonical body lives in
`cora.equipment._update_handler.make_equipment_update_handler` (load
+ authorize + fold + decide + append, with structured logging at
each boundary). This module is a thin slice-specific bind: it
supplies the command name, log prefix, and decider.

Not idempotency-wrapped: update-style commands are inherently
domain-idempotent at the aggregate level (second call hits
`AssetCannotEnterMaintenanceError`); apply only when
cached-success-on-retry semantics are needed.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._update_handler import make_equipment_update_handler
from cora.equipment.features.enter_maintenance.command import EnterMaintenance
from cora.equipment.features.enter_maintenance.decider import decide
from cora.infrastructure.deps import SharedDeps


class Handler(Protocol):
    """Callable interface every enter_maintenance handler implements."""

    async def __call__(
        self,
        command: EnterMaintenance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: SharedDeps) -> Handler:
    """Build an enter_maintenance handler closed over the shared deps."""
    return make_equipment_update_handler(
        deps,
        command_name="EnterMaintenance",
        log_prefix="enter_maintenance",
        decide_fn=decide,
    )
