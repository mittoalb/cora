"""Frame aggregate: named coordinate frame for Placement composition.

A `Frame` names a coordinate system used by `Placement` values to
express "where" a Mount or another Frame is. The first frames in any
deployment are the beamline centerlines: APS 2-BM has three
(standard 1.35 mrad, alternate 5.1 mrad at the mirror, alternate
5.23 mrad at the mirror), and the design memo's locked
`alternate-centerlines` motivation is the canonical use case.

Frames form a tree via `parent_frame_id`: root frames have
`parent_frame_id = None` (and no `placement`);
child frames carry a `Placement` that positions them relative to
their parent. The invariant ("both fields together, or both None")
is enforced at the decider.

Lifecycle: `Active | Decommissioned`. `decommission_frame` is
guarded by a projection precondition (`FrameInUseError`) so a frame
referenced by any active Mount or child Frame stays alive.

Vertical slices that operate on this aggregate live under
`cora.equipment.features.<verb>_frame/` and import from here for
state and event types.
"""

from cora.equipment.aggregates.frame.events import (
    FrameDecommissioned,
    FrameEvent,
    FramePlacementUpdated,
    FrameRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.frame.evolver import evolve, fold
from cora.equipment.aggregates.frame.read import load_frame
from cora.equipment.aggregates.frame.state import (
    FRAME_NAME_MAX_LENGTH,
    Frame,
    FrameAlreadyExistsError,
    FrameCannotDecommissionError,
    FrameCannotSupersedeError,
    FrameCannotUpdateError,
    FrameInUseError,
    FrameName,
    FrameNotFoundError,
    FrameRevisionLink,
    FrameStatus,
    InvalidFrameNameError,
    InvalidFrameRevisionError,
    InvalidFrameRootError,
)

__all__ = [
    "FRAME_NAME_MAX_LENGTH",
    "Frame",
    "FrameAlreadyExistsError",
    "FrameCannotDecommissionError",
    "FrameCannotSupersedeError",
    "FrameCannotUpdateError",
    "FrameDecommissioned",
    "FrameEvent",
    "FrameInUseError",
    "FrameName",
    "FrameNotFoundError",
    "FramePlacementUpdated",
    "FrameRegistered",
    "FrameRevisionLink",
    "FrameStatus",
    "InvalidFrameNameError",
    "InvalidFrameRevisionError",
    "InvalidFrameRootError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_frame",
    "to_payload",
]
