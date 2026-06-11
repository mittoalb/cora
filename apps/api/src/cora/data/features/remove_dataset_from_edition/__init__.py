"""Vertical slice for the `RemoveDatasetFromEdition` command."""

from cora.data.features.remove_dataset_from_edition import tool
from cora.data.features.remove_dataset_from_edition.command import (
    RemoveDatasetFromEdition,
)
from cora.data.features.remove_dataset_from_edition.decider import decide
from cora.data.features.remove_dataset_from_edition.handler import Handler, bind
from cora.data.features.remove_dataset_from_edition.route import router

__all__ = [
    "Handler",
    "RemoveDatasetFromEdition",
    "bind",
    "decide",
    "router",
    "tool",
]
