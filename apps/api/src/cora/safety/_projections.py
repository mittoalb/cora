"""Safety BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_safety_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Projections:

- `ClearanceSummaryProjection` (11a-b): clearance lifecycle
- `ClearanceTemplateSummaryProjection` (9A): clearance template metadata
"""

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry
from cora.safety.projections import (
    ClearanceSummaryProjection,
    ClearanceTemplateSummaryProjection,
)


def register_safety_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Safety-owned projection on the worker registry."""
    _ = deps
    registry.register(ClearanceSummaryProjection())
    registry.register(ClearanceTemplateSummaryProjection())


__all__ = ["register_safety_projections"]
