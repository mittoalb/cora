"""Vertical slice for the `AddPlanWire` command.

Module-as-namespace surface:

    from cora.recipe.features import add_plan_wire

    cmd = add_plan_wire.AddPlanWire(
        plan_id=...,
        source_asset_id=...,
        source_port_name="trigger_out",
        target_asset_id=...,
        target_port_name="trigger_in",
    )
    handler = add_plan_wire.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Plan.wires declares port-to-port connections between
bound Assets. See [[project_plan_wiring_design]].
"""

from cora.recipe.features.add_plan_wire import tool
from cora.recipe.features.add_plan_wire.command import AddPlanWire
from cora.recipe.features.add_plan_wire.context import PlanWireContext
from cora.recipe.features.add_plan_wire.decider import decide
from cora.recipe.features.add_plan_wire.handler import Handler, bind
from cora.recipe.features.add_plan_wire.route import router

__all__ = [
    "AddPlanWire",
    "Handler",
    "PlanWireContext",
    "bind",
    "decide",
    "router",
    "tool",
]
