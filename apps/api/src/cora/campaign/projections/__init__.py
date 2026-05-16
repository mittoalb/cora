"""Campaign BC projections.

Single-aggregate BC, single projection: CampaignSummaryProjection
backs `GET /campaigns` (list) and complements `GET /campaigns/{id}`
(which still uses fold-on-read for canonical state).

Add a new projection by creating a new module here + re-exporting its
class + adding it to `register_campaign_projections`.
"""

from cora.campaign.projections.campaign import CampaignSummaryProjection

__all__ = ["CampaignSummaryProjection"]
