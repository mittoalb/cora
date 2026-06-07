"""Application handler for the `observe_supply_status` slice.

Update-style handler. Body lives in the per-aggregate factory at
`cora.supply._supply_update_handler.make_supply_update_handler`,
same pattern as the operator-driven transition slices (degrade_supply,
mark_supply_unavailable, etc.). The factory pre-loads the Supply
aggregate, calls the pure decider, and appends the emitted events
to the event store.

Per [[project_supply_monitor_trigger_design]]: this handler is
intentionally NOT exposed via REST route or MCP tool. In-process
adapters (the future EPICS subscriber, TomoScan watchdog, etc.)
call `SupplyHandlers.observe_supply_status(...)` directly.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.supply._supply_update_handler import make_supply_update_handler
from cora.supply.aggregates.supply import TriggeredBy
from cora.supply.features.observe_supply_status.command import ObserveSupplyStatus
from cora.supply.features.observe_supply_status.decider import decide


def _monitor_triggered_by(command: ObserveSupplyStatus, _principal_id: UUID) -> TriggeredBy:
    """Monitor-triggered slices pull MonitorSourceId from the command,
    not from the request principal. The in-process adapter that drove
    the observation owns the attribution; the request principal is
    typically a service account whose identity is incidental.
    """
    return command.monitor_source_id


class Handler(Protocol):
    """Callable interface every observe_supply_status handler implements."""

    async def __call__(
        self,
        command: ObserveSupplyStatus,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an observe_supply_status handler closed over the shared deps."""
    return make_supply_update_handler(
        deps,
        command_name="ObserveSupplyStatus",
        log_prefix="observe_supply_status",
        decide_fn=decide,
        triggered_by_fn=_monitor_triggered_by,
    )
