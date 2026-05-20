"""Vertical slice for the `DemoteDataset` command (post-Q4 compensation primitive).

Module-as-namespace surface:

    from cora.data.features import demote_dataset

    cmd = demote_dataset.DemoteDataset(
        dataset_id=...,
        reason="discovered calibration error post-publication",
    )
    handler = demote_dataset.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Demotes a Dataset from Production to Retracted intent (terminal). First
concrete instantiation of the Q4 compensation-primitive pattern; see
[[project-dataset-demote-design]] for the locked design memo.
"""

from cora.data.features.demote_dataset import tool
from cora.data.features.demote_dataset.command import DemoteDataset
from cora.data.features.demote_dataset.decider import decide
from cora.data.features.demote_dataset.handler import Handler, bind
from cora.data.features.demote_dataset.route import router

__all__ = [
    "DemoteDataset",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
