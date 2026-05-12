"""Vertical slice for the `GetDataset` query.

Module-as-namespace surface, symmetric with command slices:

    from cora.data.features import get_dataset

    q = get_dataset.GetDataset(dataset_id=...)
    handler = get_dataset.bind(deps)
    dataset = await handler(q, principal_id=..., correlation_id=...)
"""

from cora.data.features.get_dataset import tool
from cora.data.features.get_dataset.handler import Handler, bind
from cora.data.features.get_dataset.query import GetDataset
from cora.data.features.get_dataset.route import router

__all__ = [
    "GetDataset",
    "Handler",
    "bind",
    "router",
    "tool",
]
