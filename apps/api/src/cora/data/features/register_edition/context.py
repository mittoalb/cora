"""Cross-aggregate context the `register_edition` decider validates against.

`EditionRegistrationContext` is built by the `register_edition` handler
from `load_dataset` calls (same-BC) for each `command.dataset_ids`
entry before reaching the pure decider. The handler raises
`DatasetNotFoundError` upstream if any id does not resolve; the
decider treats `datasets` as proof-of-existence + carries the
Datasets for the Discarded guard.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.data.aggregates.dataset import Dataset


@dataclass(frozen=True)
class EditionRegistrationContext:
    """Snapshot of cross-aggregate references at Edition-registration time."""

    datasets: dict[UUID, Dataset]
