"""Equipment BC projections.

First multi-projection BC: each aggregate gets its own file under
this package. Add a new projection by creating a new module here +
re-exporting its class + adding it to `register_equipment_projections`.
"""

from cora.equipment.projections.asset import AssetSummaryProjection
from cora.equipment.projections.asset_family_membership import (
    AssetFamilyMembershipProjection,
)
from cora.equipment.projections.family import FamilySummaryProjection
from cora.equipment.projections.frame_children import FrameChildrenProjection
from cora.equipment.projections.frame_consumers import FrameConsumersProjection
from cora.equipment.projections.frame_summary import FrameSummaryProjection

__all__ = [
    "AssetFamilyMembershipProjection",
    "AssetSummaryProjection",
    "FamilySummaryProjection",
    "FrameChildrenProjection",
    "FrameConsumersProjection",
    "FrameSummaryProjection",
]
