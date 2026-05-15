"""Procedure aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.operation.features.<verb>_procedure/` and import from here for
state and event types.

Public surface (10c-b): VOs + errors + events (genesis +
start/complete/abort) + evolver + load_procedure. 10c-b iter 2 adds
the per-step substream (entries module + ProcedureStepsLogbookOpened
envelope event). 10c-c adds projection + truncate.
"""

from cora.operation.aggregates.procedure.events import (
    ProcedureAborted,
    ProcedureCompleted,
    ProcedureEvent,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.operation.aggregates.procedure.evolver import evolve, fold
from cora.operation.aggregates.procedure.read import load_procedure
from cora.operation.aggregates.procedure.state import (
    PROCEDURE_ABORT_REASON_MAX_LENGTH,
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
    InvalidProcedureAbortReasonError,
    InvalidProcedureKindError,
    InvalidProcedureNameError,
    Procedure,
    ProcedureAbortReason,
    ProcedureAlreadyExistsError,
    ProcedureAssetDecommissionedError,
    ProcedureCannotAbortError,
    ProcedureCannotCompleteError,
    ProcedureCannotStartError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)

__all__ = [
    "PROCEDURE_ABORT_REASON_MAX_LENGTH",
    "PROCEDURE_KIND_MAX_LENGTH",
    "PROCEDURE_NAME_MAX_LENGTH",
    "InvalidProcedureAbortReasonError",
    "InvalidProcedureKindError",
    "InvalidProcedureNameError",
    "Procedure",
    "ProcedureAbortReason",
    "ProcedureAborted",
    "ProcedureAlreadyExistsError",
    "ProcedureAssetDecommissionedError",
    "ProcedureCannotAbortError",
    "ProcedureCannotCompleteError",
    "ProcedureCannotStartError",
    "ProcedureCompleted",
    "ProcedureEvent",
    "ProcedureName",
    "ProcedureNotFoundError",
    "ProcedureRegistered",
    "ProcedureStarted",
    "ProcedureStatus",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_procedure",
    "to_payload",
]
