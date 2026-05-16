"""Campaign BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_campaign_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Campaign is a single-
aggregate BC: today only `CampaignSummaryProjection` exists.
"""

from cora.campaign.projections import CampaignSummaryProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_campaign_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Campaign-owned projection on the worker registry."""
    _ = deps
    registry.register(CampaignSummaryProjection())


__all__ = ["register_campaign_projections"]
