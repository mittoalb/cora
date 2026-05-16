"""The `ListCampaigns` query: intent dataclass for keyset-paginated
list of campaigns from the `proj_campaign_summary` projection.

Five optional filters (status / intent / lead_actor_id / subject_id /
tag). The default behavior (no status passed) returns OPEN campaigns
(status IN Planned, Active, Held), matching the design memo's
"default excludes terminal states unless `?status=all`".

Cursor encodes `(registered_at, campaign_id)`. `registered_at` is set
once at CampaignRegistered (immutable), so it's a stable keyset key.

## Filters intentionally NOT in 6i-b

  - `has_run_id`: needs Run.campaign_id indexed scan on the Run
    projection (run_ids lives on the Campaign aggregate stream only;
    the projection denorm is `run_count`, not the UUID set). Per design
    memo Watch item #10, this filter lands in 6i-c with the Run
    aggregate evolution.
  - `external_ref_scheme` / `external_ref_id`: external_refs lives on
    the aggregate stream; the projection denorm is `external_id` only.
    Reverse-query by ExternalRef tuple would need a projection denorm
    table (per-campaign rows) which is deferred.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

CampaignIntentFilter = Literal[
    "Series",
    "Sweep",
    "Coordinated",
    "Block",
]

# Status carries the "all" sentinel in addition to the five real statuses.
# Handler default (None -> open set Planned+Active+Held) and "all" (no
# filter) are mapped in Python before binding.
CampaignStatusFilter = Literal[
    "Planned",
    "Active",
    "Held",
    "Closed",
    "Abandoned",
    "all",
]


@dataclass(frozen=True)
class ListCampaigns:
    """Read a keyset-paginated page of campaigns from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    status: CampaignStatusFilter | None = None
    """Optional status filter; None defaults to OPEN set in the handler.

    Pass 'all' to disable status filtering (returns every status);
    pass an exact value (Planned / Active / Held / Closed / Abandoned)
    to filter to that status only. None (default) returns the OPEN
    set: Planned + Active + Held.
    """

    intent: CampaignIntentFilter | None = None
    """Optional intent filter (one of the 4 CampaignIntent values)."""

    lead_actor_id: UUID | None = None
    """Optional lead-actor filter ('campaigns I lead')."""

    subject_id: UUID | None = None
    """Optional subject filter (loose ref; matches the operator-asserted
    `Campaign.subject_id`, not derived from member Runs)."""

    tag: str | None = None
    """Optional tag filter; matches any campaign whose `tags` array contains this value."""
