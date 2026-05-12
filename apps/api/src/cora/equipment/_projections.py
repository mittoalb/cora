"""Equipment BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_equipment_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Equipment is the first
multi-aggregate BC; only Asset has a projection today, Capability's
arrives in 8e-3b.
"""

from cora.equipment.projections import AssetSummaryProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_equipment_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Equipment-owned projection on the worker registry."""
    _ = deps
    registry.register(AssetSummaryProjection())


__all__ = ["register_equipment_projections"]
