"""Trust bounded context.

Owns the authorization concerns of CORA: which principals are allowed
to do what, where. Authentication (who a principal *is*) lives in the
Access BC. Trust answers "may this principal issue this command via
this conduit" against `Zone` / `Conduit` / `Policy` aggregates.

Phase 3a ships the `Zone` aggregate with `define_zone`. `Conduit` and
`Policy` plus the real `TrustAuthorize` adapter (replacing
`AllowAllAuthorize`) land in subsequent sub-phases. Until then the
Authorize port stays at the AllowAll stub and Trust just owns its own
Zone definitions.

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver
    features/<verb>_<noun>/   -- vertical slice: command + decider + handler + route + tool
    wire.py                   -- TrustHandlers bundle + wire_trust(deps)
    routes.py                 -- register_trust_routes(app)
"""

from cora.trust.authorize import TrustAuthorize
from cora.trust.errors import UnauthorizedError
from cora.trust.routes import register_trust_routes
from cora.trust.tools import register_trust_tools
from cora.trust.wire import TrustHandlers, wire_trust

__all__ = [
    "TrustAuthorize",
    "TrustHandlers",
    "UnauthorizedError",
    "register_trust_routes",
    "register_trust_tools",
    "wire_trust",
]
