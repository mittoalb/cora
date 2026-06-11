"""Data BC's projection-registration entry point."""

from cora.data.projections import DatasetSummaryProjection, DistributionSummaryProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_data_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Data-owned projection on the worker registry."""
    _ = deps
    registry.register(DatasetSummaryProjection())
    registry.register(DistributionSummaryProjection())


__all__ = ["register_data_projections"]
