"""Vertical slice for the `RemovePlanWire` command.

Module-as-namespace surface:

    from cora.recipe.features import remove_plan_wire

    cmd = remove_plan_wire.RemovePlanWire(
        plan_id=...,
        source_asset_id=...,
        source_port_name="trigger_out",
        target_asset_id=...,
        target_port_name="trigger_in",
    )
    handler = remove_plan_wire.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Mirror of `add_plan_wire`. See [[project_plan_wiring_design]].
"""

from cora.recipe.features.remove_plan_wire import tool
from cora.recipe.features.remove_plan_wire.command import RemovePlanWire
from cora.recipe.features.remove_plan_wire.decider import decide
from cora.recipe.features.remove_plan_wire.handler import Handler, bind
from cora.recipe.features.remove_plan_wire.route import router

__all__ = [
    "Handler",
    "RemovePlanWire",
    "bind",
    "decide",
    "router",
    "tool",
]
