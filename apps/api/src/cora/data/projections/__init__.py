"""Data BC projections.

Three projection writers:
  - DatasetSummaryProjection: folds Dataset lifecycle events into
    proj_data_dataset_summary.
  - DistributionSummaryProjection: folds DistributionRegistered into
    proj_data_distribution_summary.
  - EditionSummaryProjection: folds Edition 6-event lifecycle into
    proj_data_edition_summary.
"""

from cora.data.projections.distribution_summary import DistributionSummaryProjection
from cora.data.projections.edition_summary import EditionSummaryProjection
from cora.data.projections.summary import DatasetSummaryProjection

__all__ = [
    "DatasetSummaryProjection",
    "DistributionSummaryProjection",
    "EditionSummaryProjection",
]
