"""Vertical slice for the `PromoteDataset` command (Phase 7e).

Module-as-namespace surface:

    from cora.data.features import promote_dataset

    cmd = promote_dataset.PromoteDataset(
        dataset_id=...,
        reason="passed peer review for Smith et al 2026",
    )
    handler = promote_dataset.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Promotes a Dataset from Trial to Production intent. See
[[project_dataset_lineage_design]] for the locked design memo.
"""

from cora.data.features.promote_dataset import tool
from cora.data.features.promote_dataset.command import PromoteDataset
from cora.data.features.promote_dataset.context import PromotionContext
from cora.data.features.promote_dataset.decider import decide
from cora.data.features.promote_dataset.handler import Handler, bind
from cora.data.features.promote_dataset.route import router

__all__ = [
    "Handler",
    "PromoteDataset",
    "PromotionContext",
    "bind",
    "decide",
    "router",
    "tool",
]
