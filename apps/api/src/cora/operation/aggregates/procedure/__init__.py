"""Procedure aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.operation.features.<verb>_procedure/` and import from here for
state and event types.

Public surface (10c-a): VOs + errors + events + evolver +
load_procedure. 10c-b adds transition events / errors and the
per-step substream (entries module). 10c-c adds projection.
"""

from cora.operation.aggregates.procedure.events import (
    ProcedureEvent,
    ProcedureRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.operation.aggregates.procedure.evolver import evolve, fold
from cora.operation.aggregates.procedure.read import load_procedure
from cora.operation.aggregates.procedure.state import (
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
    InvalidProcedureKindError,
    InvalidProcedureNameError,
    Procedure,
    ProcedureAlreadyExistsError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)

__all__ = [
    "PROCEDURE_KIND_MAX_LENGTH",
    "PROCEDURE_NAME_MAX_LENGTH",
    "InvalidProcedureKindError",
    "InvalidProcedureNameError",
    "Procedure",
    "ProcedureAlreadyExistsError",
    "ProcedureEvent",
    "ProcedureName",
    "ProcedureNotFoundError",
    "ProcedureRegistered",
    "ProcedureStatus",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_procedure",
    "to_payload",
]
