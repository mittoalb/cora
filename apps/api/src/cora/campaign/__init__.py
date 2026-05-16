"""Campaign bounded context.

Owns the Campaign aggregate: the operator-declared coordinated
container above Run (in-situ heating series, operando battery
measurement, parametric sweep, multi-modal acquisition,
proposal-block scheduling envelope).

  - `Campaign` aggregate (6i-a): identity + name + closed intent
    enum + lead actor + loose subject ref + tags + external refs +
    optional external_id + run_ids (forward-compat empty) +
    5-state FSM `Planned -> Active <-> Held -> Closed | Abandoned`.

Distinct BC from Recipe per `[[project_campaign_design]]`: audience-
and-vocabulary separation. Recipe BC owns the pre-execution template
ladder (Method / Practice / Plan; design surface for recipe authors);
Campaign is a post-execution coordination layer (study surface for
operators / PIs after Plans exist). Same operators, different mental
modes.

Phase 6i-a ships the BC scaffold + 7 slices:
  - register_campaign  (genesis -> Planned)
  - get_campaign       (read; fold-on-read)
  - start_campaign     (Planned -> Active)
  - hold_campaign      (Active -> Held; reason)
  - resume_campaign    (Held -> Active)
  - close_campaign     (Active | Held -> Closed; normal terminal)
  - abandon_campaign   (Planned | Active | Held -> Abandoned;
                        early terminal with REQUIRED reason)

Phase 6i-b adds the projection + `list_campaigns` slice.
Phase 6i-c adds the cross-aggregate membership slices
(`add_run_to_campaign` / `remove_run_from_campaign`) plus Run
aggregate evolution (additive `campaign_id` field).

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver, read
    features/<verb>_<noun>/   -- vertical slice: command/query + decider? + handler + route + tool
    wire.py                   -- CampaignHandlers bundle + wire_campaign(deps)
    routes.py                 -- register_campaign_routes(app)
    tools.py                  -- register_campaign_tools(mcp, get_handlers=...)
"""

from cora.campaign.errors import UnauthorizedError
from cora.campaign.routes import register_campaign_routes
from cora.campaign.tools import register_campaign_tools
from cora.campaign.wire import CampaignHandlers, wire_campaign

__all__ = [
    "CampaignHandlers",
    "UnauthorizedError",
    "register_campaign_routes",
    "register_campaign_tools",
    "wire_campaign",
]
