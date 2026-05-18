"""Calibration BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_calibration_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Calibration is a single-
aggregate BC: today only `CalibrationSummaryProjection` exists.
"""

from cora.calibration.projections import CalibrationSummaryProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_calibration_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Calibration-owned projection on the worker registry."""
    _ = deps
    registry.register(CalibrationSummaryProjection())


__all__ = ["register_calibration_projections"]
