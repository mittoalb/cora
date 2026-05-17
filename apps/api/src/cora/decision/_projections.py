"""Decision BC's projection-registration entry point."""

from cora.decision.projections import DecisionRatingsProjection, DecisionSummaryProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_decision_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Decision-owned projection on the worker registry."""
    _ = deps
    registry.register(DecisionSummaryProjection())
    registry.register(DecisionRatingsProjection())


__all__ = ["register_decision_projections"]
