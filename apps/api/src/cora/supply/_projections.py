"""Supply BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_supply_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Supply is a single-
aggregate BC: today only `SupplySummaryProjection` exists.
"""

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry
from cora.supply.projections import SupplySummaryProjection


def register_supply_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Supply-owned projection on the worker registry."""
    _ = deps
    registry.register(SupplySummaryProjection())


__all__ = ["register_supply_projections"]
