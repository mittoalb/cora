"""Cross-aggregate context the `remove_run_from_campaign` decider validates against.

Same shape as `add_run_to_campaign`'s context (duplicated per slice-
independence; the Caution + Safety precedent has separate contexts
per slice). Carries the loaded Campaign + Run + their stream versions
for the cross-aggregate atomic `append_streams` write.

See `cora.campaign.features.add_run_to_campaign.context` for the
field-semantics docstring.
"""

from dataclasses import dataclass

from cora.campaign.aggregates.campaign import Campaign
from cora.run.aggregates.run import Run


@dataclass(frozen=True)
class CampaignMembershipContext:
    """Snapshot of both aggregates + their stream versions at membership-mutation time."""

    campaign: Campaign
    campaign_version: int
    run: Run
    run_version: int
