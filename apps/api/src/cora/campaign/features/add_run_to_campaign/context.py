"""Cross-aggregate context the `add_run_to_campaign` decider validates against.

`CampaignMembershipContext` is built by the `add_run_to_campaign`
handler from a `load_campaign(...)` + `load_run(...)` + raw
`event_store.load(...)` calls before reaching the pure decider. The
decider treats the loaded aggregates as opaque domain data and
validates the membership preconditions without performing any I/O.

Per the canonical cross-aggregate-validation pattern documented in
CONTRIBUTING.md and mirrored from Safety's `ClearanceAmendmentContext`
(11a-c-2). Same shape is reused by `remove_run_from_campaign`
(duplicated module per slice-independence; the Caution + Safety
precedent has separate contexts per slice).

## Field semantics

  - `campaign`: the Campaign being mutated. Decider rejects if not in
    `{Planned, Active, Held}` (`CampaignCannotAddRunError`). MUST not
    be None (handler raises `CampaignNotFoundError` before constructing
    the context).
  - `campaign_version`: the Campaign stream's current event-store
    version at load time. Passed straight through to
    `EventStore.append_streams` as the expected_version for the
    Campaign's `CampaignRunAdded` append. Optimistic-concurrency guard
    against a concurrent transition on the Campaign stream.
  - `run`: the Run being added. Decider rejects if not None and
    already-assigned-to-different-campaign
    (`RunAlreadyAssignedToCampaignError`). MUST not be None (handler
    raises `RunNotFoundError` before constructing).
  - `run_version`: the Run stream's current event-store version at
    load time. Used as the expected_version for the Run's
    `RunAddedToCampaign` append.
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
