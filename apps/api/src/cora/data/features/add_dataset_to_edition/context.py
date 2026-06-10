"""Slice-local cross-aggregate context for `add_dataset_to_edition`."""

from dataclasses import dataclass

from cora.data.aggregates.dataset import Dataset


@dataclass(frozen=True)
class AddDatasetToEditionContext:
    """The Dataset peer pre-loaded by the handler for the decider."""

    dataset: Dataset
