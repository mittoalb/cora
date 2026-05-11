"""Run aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.run.features.<verb>_run/` and import from here for state and
event types. The `RunStartContext` cross-aggregate value object
lives at `cora.run.features.start_run.context` (slice-local; only
start_run needs it today).
"""

from cora.run.aggregates.run.events import (
    RunAborted,
    RunCompleted,
    RunEvent,
    RunStarted,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.run.aggregates.run.evolver import evolve, fold
from cora.run.aggregates.run.read import load_run
from cora.run.aggregates.run.state import (
    RUN_ABORT_REASON_MAX_LENGTH,
    RUN_NAME_MAX_LENGTH,
    InvalidRunAbortReasonError,
    InvalidRunNameError,
    PlanDeprecatedError,
    Run,
    RunAbortReason,
    RunAlreadyExistsError,
    RunAssetDecommissionedError,
    RunCannotAbortError,
    RunCannotCompleteError,
    RunCapabilitiesNotSatisfiedError,
    RunName,
    RunNotFoundError,
    RunStatus,
    SubjectNotMountableError,
)

__all__ = [
    "RUN_ABORT_REASON_MAX_LENGTH",
    "RUN_NAME_MAX_LENGTH",
    "InvalidRunAbortReasonError",
    "InvalidRunNameError",
    "PlanDeprecatedError",
    "Run",
    "RunAbortReason",
    "RunAborted",
    "RunAlreadyExistsError",
    "RunAssetDecommissionedError",
    "RunCannotAbortError",
    "RunCannotCompleteError",
    "RunCapabilitiesNotSatisfiedError",
    "RunCompleted",
    "RunEvent",
    "RunName",
    "RunNotFoundError",
    "RunStarted",
    "RunStatus",
    "SubjectNotMountableError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_run",
    "to_payload",
]
