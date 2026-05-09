"""Access bounded context.

Owns the identity and authentication concerns of CORA: who an actor is
and how they are recognized. Authorization (which actors can do what)
lives in the Trust BC; Access only answers "is this a known actor".

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver
    features/<verb>_<noun>/   -- vertical slice: command + event + decider + handler + route
    wire.py                   -- AccessHandlers bundle + wire_access(deps)
    routes.py                 -- register_access_routes(app)
"""

from cora.access.routes import register_access_routes
from cora.access.wire import AccessHandlers, wire_access

__all__ = [
    "AccessHandlers",
    "register_access_routes",
    "wire_access",
]
