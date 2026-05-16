"""Caution BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_caution_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Caution is a single-
aggregate BC: today only `CautionActiveProjection` exists.
"""

from cora.caution.projections import CautionActiveProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_caution_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Caution-owned projection on the worker registry."""
    _ = deps
    registry.register(CautionActiveProjection())


__all__ = ["register_caution_projections"]
