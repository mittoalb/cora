"""Monitor-driven Supply status observation (in-process inbound port).

Per [[project_supply_monitor_trigger_design]]: the `observe_supply_status`
slice is the Supply BC's inbound port (Port B) for sensor-driven
transitions. Called by in-process adapters (the future EPICS subscriber
per 2-BM adapter #1, a TomoScan watchdog, any future facility-bridge)
to flip a Supply's status without operator intervention. Reuses the
existing transition event classes with `trigger="Monitor"` and a
`monitor_ref` audit field identifying the source.

Per the design lock: NO REST route, NO MCP tool. Operators have
buttons; machines have ports. Adapters call this slice directly via
`SupplyHandlers.observe_supply_status(...)`.
"""

from cora.supply.features.observe_supply_status import tool
from cora.supply.features.observe_supply_status.command import ObserveSupplyStatus
from cora.supply.features.observe_supply_status.decider import decide
from cora.supply.features.observe_supply_status.handler import Handler, bind
from cora.supply.features.observe_supply_status.route import router

__all__ = [
    "Handler",
    "ObserveSupplyStatus",
    "bind",
    "decide",
    "router",
    "tool",
]
