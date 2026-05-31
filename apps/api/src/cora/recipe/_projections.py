"""Recipe BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_recipe_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Recipe is the second
multi-aggregate BC after Equipment: each of Method / Practice /
Plan has its own projection module under
`cora.recipe.projections`, all registered here.
"""

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry
from cora.recipe.projections import (
    CapabilitySummaryProjection,
    MethodSummaryProjection,
    PlanSummaryProjection,
    PracticeSummaryProjection,
)


def register_recipe_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Recipe-owned projection on the worker registry."""
    _ = deps
    registry.register(MethodSummaryProjection())
    registry.register(PracticeSummaryProjection())
    registry.register(PlanSummaryProjection())
    registry.register(CapabilitySummaryProjection())


__all__ = ["register_recipe_projections"]
