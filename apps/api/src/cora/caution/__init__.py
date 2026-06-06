"""Caution bounded context.

Owns operator-authored tribal-knowledge cautions in CORA:

  - `Caution` aggregate: an operator-authored note attached to an
    Asset or a Procedure (the hexapod-stalls-below-0.5mm/s family).
    3-state lightweight FSM (`Active -> Superseded | Retired`);
    supersession IS the edit path via cross-aggregate atomic write
    (mirrors Safety BC's `amend_clearance`).

Distinct BC from Safety per [[project_caution_design]]: audience
separation (operator vocabulary vs ESH-officer vocabulary) and
lifecycle weight asymmetry (3-state lightweight vs 8-state formal
FSM) both forbid co-tenancy.

Slices: `register_caution` (genesis -> Active), `supersede_caution`
(cross-aggregate; parent Active -> Superseded, new child genesis with
`parent_id`), `retire_caution` (Active -> Retired),
`get_caution` (fold-on-read), `list_cautions` (projection-backed).
Run-start integration is non-blocking via the `CautionLookup` port
(mirrors `ClearanceLookup`).

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver, read
    features/<verb>_<noun>/   -- vertical slice: command/query + decider? + handler + route + tool
    wire.py                   -- CautionHandlers bundle + wire_caution(deps)
    routes.py                 -- register_caution_routes(app)
    tools.py                  -- register_caution_tools(mcp, get_handlers=...)
    _caution_dtos.py          -- BC-private shared Pydantic discriminated TargetDTO
"""

from cora.caution._projections import register_caution_projections
from cora.caution.errors import UnauthorizedError
from cora.caution.routes import register_caution_routes
from cora.caution.tools import register_caution_tools
from cora.caution.wire import CautionHandlers, wire_caution

__all__ = [
    "CautionHandlers",
    "UnauthorizedError",
    "register_caution_projections",
    "register_caution_routes",
    "register_caution_tools",
    "wire_caution",
]
