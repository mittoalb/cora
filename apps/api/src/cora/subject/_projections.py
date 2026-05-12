"""Subject BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_subject_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry with every Subject BC
projection.
"""

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry
from cora.subject.projections import SubjectSummaryProjection


def register_subject_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Subject-owned projection on the worker registry."""
    _ = deps  # reserved for future projections needing Kernel collaborators
    registry.register(SubjectSummaryProjection())


__all__ = ["register_subject_projections"]
