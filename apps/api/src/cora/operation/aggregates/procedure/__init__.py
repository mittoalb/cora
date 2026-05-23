"""Procedure aggregate: state, status enum, errors, events, evolver, read repo, entries.

Vertical slices that operate on this aggregate live under
`cora.operation.features.<verb>_procedure/` and import from here for
state and event types.

Public surface: VOs + errors + events (genesis +
start/complete/abort/truncate + steps lazy-open envelope) + evolver +
load_procedure + per-step logbook entries (StepStore port +
InMemory + Postgres adapters + ProcedureStep dataclass) + projection.
"""

from cora.operation.aggregates.procedure.entries import (
    InMemoryStepStore,
    PostgresStepStore,
    ProcedureStep,
    StepStore,
)
from cora.operation.aggregates.procedure.events import (
    ProcedureAborted,
    ProcedureCompleted,
    ProcedureEvent,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStepsLogbookOpened,
    ProcedureTruncated,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.operation.aggregates.procedure.evolver import evolve, fold
from cora.operation.aggregates.procedure.read import load_procedure
from cora.operation.aggregates.procedure.state import (
    LOGBOOK_KIND_STEPS,
    PROCEDURE_ABORT_REASON_MAX_LENGTH,
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
    PROCEDURE_TRUNCATE_REASON_MAX_LENGTH,
    STEP_KIND_VALUES,
    STEPS_LOGBOOK_SCHEMA,
    InvalidProcedureAbortReasonError,
    InvalidProcedureInterruptedAtError,
    InvalidProcedureKindError,
    InvalidProcedureNameError,
    InvalidProcedureTruncateReasonError,
    InvalidStepKindError,
    Procedure,
    ProcedureAbortReason,
    ProcedureAlreadyExistsError,
    ProcedureAssetDecommissionedError,
    ProcedureCannotAbortError,
    ProcedureCannotCompleteError,
    ProcedureCannotStartError,
    ProcedureCannotTruncateError,
    ProcedureCapabilityExecutorMismatchError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
    ProcedureStepsLogbookClosedError,
    ProcedureTruncateReason,
    StepKind,
)

__all__ = [
    "LOGBOOK_KIND_STEPS",
    "PROCEDURE_ABORT_REASON_MAX_LENGTH",
    "PROCEDURE_KIND_MAX_LENGTH",
    "PROCEDURE_NAME_MAX_LENGTH",
    "PROCEDURE_TRUNCATE_REASON_MAX_LENGTH",
    "STEPS_LOGBOOK_SCHEMA",
    "STEP_KIND_VALUES",
    "InMemoryStepStore",
    "InvalidProcedureAbortReasonError",
    "InvalidProcedureInterruptedAtError",
    "InvalidProcedureKindError",
    "InvalidProcedureNameError",
    "InvalidProcedureTruncateReasonError",
    "InvalidStepKindError",
    "PostgresStepStore",
    "Procedure",
    "ProcedureAbortReason",
    "ProcedureAborted",
    "ProcedureAlreadyExistsError",
    "ProcedureAssetDecommissionedError",
    "ProcedureCannotAbortError",
    "ProcedureCannotCompleteError",
    "ProcedureCannotStartError",
    "ProcedureCannotTruncateError",
    "ProcedureCapabilityExecutorMismatchError",
    "ProcedureCompleted",
    "ProcedureEvent",
    "ProcedureName",
    "ProcedureNotFoundError",
    "ProcedureRegistered",
    "ProcedureStarted",
    "ProcedureStatus",
    "ProcedureStep",
    "ProcedureStepsLogbookClosedError",
    "ProcedureStepsLogbookOpened",
    "ProcedureTruncateReason",
    "ProcedureTruncated",
    "StepKind",
    "StepStore",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_procedure",
    "to_payload",
]
