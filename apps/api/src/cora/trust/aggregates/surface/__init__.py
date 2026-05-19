"""Surface aggregate: state, errors, events, evolver, read repo.

A `Surface` is a process-level arrival point (HTTP socket, MCP
stdio, MCP streamable-http). Sibling to Zone / Conduit / Policy in
the Trust BC. See `state.py` for the design lock + see
`memory/project_conduit_injection_design.md` for the decomposition
rationale.
"""

from cora.trust.aggregates.surface.events import (
    SurfaceDefined,
    SurfaceEvent,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.trust.aggregates.surface.evolver import evolve, fold
from cora.trust.aggregates.surface.read import load_surface
from cora.trust.aggregates.surface.state import (
    SURFACE_NAME_MAX_LENGTH,
    InvalidSurfaceNameError,
    Surface,
    SurfaceAlreadyExistsError,
    SurfaceName,
    SurfaceStatus,
)
from cora.trust.aggregates.surface.surface_kind import SurfaceKind

__all__ = [
    "SURFACE_NAME_MAX_LENGTH",
    "InvalidSurfaceNameError",
    "Surface",
    "SurfaceAlreadyExistsError",
    "SurfaceDefined",
    "SurfaceEvent",
    "SurfaceKind",
    "SurfaceName",
    "SurfaceStatus",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_surface",
    "to_payload",
]
