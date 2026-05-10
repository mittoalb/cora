"""Subject bounded context.

The entity being measured, observed, or studied. Generic across
science domains: materials samples, biological specimens,
manufactured parts (including in-flight AM prints being formed
during the experiment), astronomical targets, computational subjects.
Carries identity that crosses Run boundaries.

Phase 4a ships the Subject aggregate + `register_subject`. Status
transitions (mount / measure / remove / return / store / discard)
land in 4b-4d; the get_subject query in 4e. `hazard`, `custody`,
`owner`, and the in-situ-during-Run substream defer to Phase 4f+.

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver
    features/<verb>_<noun>/   -- vertical slice: command + decider + handler + route + tool
    wire.py                   -- SubjectHandlers bundle + wire_subject(deps)
    routes.py                 -- register_subject_routes(app)
"""

from cora.subject.errors import UnauthorizedError
from cora.subject.routes import register_subject_routes
from cora.subject.tools import register_subject_tools
from cora.subject.wire import SubjectHandlers, wire_subject

__all__ = [
    "SubjectHandlers",
    "UnauthorizedError",
    "register_subject_routes",
    "register_subject_tools",
    "wire_subject",
]
