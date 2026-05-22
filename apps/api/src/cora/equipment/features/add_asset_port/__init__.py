"""Vertical slice for the `AddAssetPort` command.

Module-as-namespace surface:

    from cora.equipment.features import add_asset_port

    cmd = add_asset_port.AddAssetPort(
        asset_id=...,
        port_name="trigger_in",
        direction=PortDirection.INPUT,
        signal_type="TTL",
    )
    handler = add_asset_port.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Ports declare what typed connection points the equipment
exposes; Plan.wiring will reference these by name to declare
port-to-port connections.
"""

from cora.equipment.features.add_asset_port import tool
from cora.equipment.features.add_asset_port.command import AddAssetPort
from cora.equipment.features.add_asset_port.decider import decide
from cora.equipment.features.add_asset_port.handler import Handler, bind
from cora.equipment.features.add_asset_port.route import router

__all__ = [
    "AddAssetPort",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
