"""Subject bounded context.

The entity being measured, observed, or studied. Generic across
science domains: materials samples, biological specimens,
manufactured parts (including in-flight AM prints being formed
during the experiment), astronomical targets, computational subjects.
Carries identity that crosses Run boundaries.

Operationally complete as a state machine after Phase 4a-e:
7 commands (`register_subject` + the 6 transitions
`mount` / `measure` / `remove` / `return` / `store` / `discard`)
plus `get_subject` (read side). Full lifecycle: `Received -> Mounted
-> Measured -> Removed -> Returned | Stored | Discarded`. Update-style
handlers share `_update_handler.make_subject_update_handler` (see its
docstring for the factory's contract). `hazard`, `custody`, `owner`,
and the in-situ-during-Run observation channel defers to Phase 4f+.

Layout:
    aggregates/<aggregate>/   -- aggregate state, events union, evolver
    features/<verb>_<noun>/   -- vertical slice: command + decider + handler + route + tool
    _update_handler.py        -- shared update-style handler factory (4b-d slices)
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
