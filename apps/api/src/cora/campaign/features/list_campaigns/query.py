"""The `ListCampaigns` query: intent dataclass for keyset-paginated
list of campaigns from the `proj_campaign_summary` projection.

Five optional filters in canonical form:

  - intent / lead_actor_id / subject_id / tag (single-value, exact match)
  - statuses (list of acceptable status values; None == no filter)

User-facing UX (the `status` sentinel including 'all', the
default-to-OPEN-set behavior) lives at the route/MCP-tool
boundary, NOT in this dataclass. The route translates user input
into the canonical list-typed `statuses` field before constructing
the query (mirrors the list_cautions force-conform precedent).

The query dataclass is the canonical internal contract: anything
constructing `ListCampaigns(...)` directly (tests, internal code)
sees a uniform "None means no filter" semantic for every field,
matching every other list-query slice in the codebase.

Cursor encodes `(registered_at, campaign_id)`. `registered_at` is
set once at CampaignRegistered (immutable), so it's a stable
keyset key.

## Filters intentionally deferred

  - `has_run_id`: needs Run.campaign_id indexed scan on the Run
    projection (run_ids lives on the Campaign aggregate stream
    only; the projection denorm is `run_count`, not the UUID set).
    Per design memo Watch item #10, this filter lands with
    the Run aggregate evolution.
  - `external_ref_scheme` / `external_ref_id`: external_refs lives
    on the aggregate stream; the projection denorm is `external_id`
    only. Reverse-query by ExternalRef tuple would need a
    projection denorm table (per-campaign rows) which is deferred.
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

CampaignStatusFilter = Literal[
    "Planned",
    "Active",
    "Held",
    "Closed",
    "Abandoned",
]


@dataclass(frozen=True)
class ListCampaigns:
    """Read a keyset-paginated page of campaigns from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    statuses: list[CampaignStatusFilter] | None = None
    """Optional set of acceptable status values; None == no filter,
    empty list also treated as no filter by the factory.

    Route applies the operator-UX default (OPEN set:
    [Planned, Active, Held]) when the request omits the status
    param; the user opts into the full history by passing the
    route-level `?status=all` sentinel which the route translates
    to None here, or by passing every status explicitly."""

    intent: CampaignIntentFilter | None = None
    """Optional intent filter (one of the 4 CampaignIntent values)."""

    lead_actor_id: UUID | None = None
    """Optional lead-actor filter ('campaigns I lead')."""

    subject_id: UUID | None = None
    """Optional subject filter (loose ref; matches the operator-asserted
    `Campaign.subject_id`, not derived from member Runs)."""

    tag: str | None = None
    """Optional tag filter; matches any campaign whose `tags` array contains this value."""
