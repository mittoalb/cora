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
    RunHeld,
    RunResumed,
    RunStarted,
    RunStopped,
    RunTruncated,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.run.aggregates.run.evolver import evolve, fold
from cora.run.aggregates.run.parameters_validation import (
    validate_effective_parameters_against_method_schema,
)
from cora.run.aggregates.run.read import load_run
from cora.run.aggregates.run.state import (
    RUN_ABORT_REASON_MAX_LENGTH,
    RUN_NAME_MAX_LENGTH,
    RUN_STOP_REASON_MAX_LENGTH,
    RUN_TRUNCATE_REASON_MAX_LENGTH,
    InvalidRunAbortReasonError,
    InvalidRunInterruptedAtError,
    InvalidRunNameError,
    InvalidRunParametersError,
    InvalidRunStopReasonError,
    InvalidRunTruncateReasonError,
    PlanDeprecatedError,
    Run,
    RunAbortReason,
    RunAlreadyExistsError,
    RunAssetDecommissionedError,
    RunCannotAbortError,
    RunCannotCompleteError,
    RunCannotHoldError,
    RunCannotResumeError,
    RunCannotStopError,
    RunCannotTruncateError,
    RunCapabilitiesNotSatisfiedError,
    RunName,
    RunNotFoundError,
    RunStatus,
    RunStopReason,
    RunTruncateReason,
    SubjectNotMountableError,
)

__all__ = [
    "RUN_ABORT_REASON_MAX_LENGTH",
    "RUN_NAME_MAX_LENGTH",
    "RUN_STOP_REASON_MAX_LENGTH",
    "RUN_TRUNCATE_REASON_MAX_LENGTH",
    "InvalidRunAbortReasonError",
    "InvalidRunInterruptedAtError",
    "InvalidRunNameError",
    "InvalidRunParametersError",
    "InvalidRunStopReasonError",
    "InvalidRunTruncateReasonError",
    "PlanDeprecatedError",
    "Run",
    "RunAbortReason",
    "RunAborted",
    "RunAlreadyExistsError",
    "RunAssetDecommissionedError",
    "RunCannotAbortError",
    "RunCannotCompleteError",
    "RunCannotHoldError",
    "RunCannotResumeError",
    "RunCannotStopError",
    "RunCannotTruncateError",
    "RunCapabilitiesNotSatisfiedError",
    "RunCompleted",
    "RunEvent",
    "RunHeld",
    "RunName",
    "RunNotFoundError",
    "RunResumed",
    "RunStarted",
    "RunStatus",
    "RunStopReason",
    "RunStopped",
    "RunTruncateReason",
    "RunTruncated",
    "SubjectNotMountableError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_run",
    "to_payload",
    "validate_effective_parameters_against_method_schema",
]
