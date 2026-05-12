"""Vertical slice for the `DiscardDataset` command.

Module-as-namespace surface:

    from cora.data.features import discard_dataset

    cmd = discard_dataset.DiscardDataset(
        dataset_id=...,
        reason="GDPR Article 17 erasure request",
    )
    handler = discard_dataset.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.data.features.discard_dataset import tool
from cora.data.features.discard_dataset.command import DiscardDataset
from cora.data.features.discard_dataset.decider import decide
from cora.data.features.discard_dataset.handler import Handler, bind
from cora.data.features.discard_dataset.route import router

__all__ = [
    "DiscardDataset",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
