"""Vertical slice for the `GetAssetIntegrationView` query.

Module-as-namespace surface:

    from cora.equipment.features import get_asset_integration_view

    q = get_asset_integration_view.GetAssetIntegrationView(asset_id=...)
    handler = get_asset_integration_view.bind(deps)
    view = await handler(q, principal_id=..., correlation_id=...)

v1 of the MTP-style read-model bundle per [[project-asset-integration-view-design]].
Read-time composition (no new projection table, no new subscribers) that
consolidates the 7-query operator/agent walkthrough into one bundle:
Asset core + families (id/name/affordances) + ports + settings +
active Cautions + applicable Capabilities.

Promotion to a denormalized projection (v2) is the explicit upgrade
path; trigger is documented in the design memo.
"""

from cora.equipment.features.get_asset_integration_view import tool
from cora.equipment.features.get_asset_integration_view.handler import Handler, bind
from cora.equipment.features.get_asset_integration_view.query import GetAssetIntegrationView
from cora.equipment.features.get_asset_integration_view.route import router
from cora.equipment.features.get_asset_integration_view.view import (
    AssetIntegrationView,
    CapabilityView,
    CautionView,
    FamilyView,
    PortView,
)

__all__ = [
    "AssetIntegrationView",
    "CapabilityView",
    "CautionView",
    "FamilyView",
    "GetAssetIntegrationView",
    "Handler",
    "PortView",
    "bind",
    "router",
    "tool",
]
