"""Safety bounded context.

Owns regulatory safety-form gating in CORA:

  - `Clearance` aggregate (11a-a): a facility safety form (APS ESAF,
    NSLS-II SAF, ESRF A-form / SAF, MAX IV DUO / ESRA, DLS ERA / PLHD,
    DESY DOOR, ALS ESAF, SLAC BTR, SPring-8 Form 9). One unified
    aggregate carries form data + lifecycle state + multi-step review
    chain + the polymorphic set of CORA aggregates and external IDs
    the form binds to.

Reverses the BC map's earlier "no standalone Safety BC" stance per
the principled trigger documented at BC map line 119:
hazard-specific lifecycle/approval workflows (review, approve, expire,
amend, multi-step reviewer chains) for the 9 facility forms cannot fit
in Trust.Zone shape. See [[project_safety_clearance_design]] for the
full lock + research grounding.

Safety BC has no projection at 11a-a (lands in 11a-b alongside the
FSM-closure transitions and `list_clearances`).

Layout:
    aggregates/clearance/      -- state, events union, evolver, read
    aggregates/clearance/      -- + hazard_classification VO (consumed by kernel + features)
    features/<verb>_<noun>/    -- vertical slice: command/query + decider? + handler + route + tool
    wire.py                    -- SafetyHandlers bundle + wire_safety(deps)
    routes.py                  -- register_safety_routes(app)
    tools.py                   -- register_safety_tools(mcp, get_handlers=...)
"""

from cora.safety._projections import register_safety_projections
from cora.safety.errors import UnauthorizedError
from cora.safety.routes import register_safety_routes
from cora.safety.tools import register_safety_tools
from cora.safety.wire import SafetyHandlers, wire_safety

__all__ = [
    "SafetyHandlers",
    "UnauthorizedError",
    "register_safety_projections",
    "register_safety_routes",
    "register_safety_tools",
    "wire_safety",
]
