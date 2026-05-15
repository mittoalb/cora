"""Safety BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_safety_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. 11a-b ships one projection
(`ClearanceSummaryProjection`).
"""

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry
from cora.safety.projections import ClearanceSummaryProjection


def register_safety_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Safety-owned projection on the worker registry."""
    _ = deps
    registry.register(ClearanceSummaryProjection())


__all__ = ["register_safety_projections"]
