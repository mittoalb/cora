"""HTTP setup for the Operation BC.

`register_operation_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, `ConcurrencyError`, and `AssetNotFoundError`
(Equipment-BC) are infra-layer / cross-BC errors registered by their
owning BC. They produce the same JSON shape regardless of which BC
raised them, so Operation does not re-register them.

## Loop-collapse pattern

Operation owns one aggregate (Procedure) plus its per-step logbook.
Five error families share the same response shape and get collapsed
via the Trust / Equipment / Supply-style loop pattern:

  - 400 (validation): InvalidProcedureName, InvalidProcedureKind,
    InvalidProcedureAbortReason, InvalidProcedureTruncateReason,
    InvalidProcedureInterruptedAt, InvalidStepKind
  - 404 (load miss): ProcedureNotFound
  - 409 (defensive guard for AlreadyExists): ProcedureAlreadyExists
  - 409 (transition guards): ProcedureCannotStart,
    ProcedureCannotComplete, ProcedureCannotAbort,
    ProcedureCannotTruncate, ProcedureAssetDecommissioned,
    ProcedureStepsLogbookClosed
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.operation.aggregates.procedure import (
    InvalidProcedureAbortReasonError,
    InvalidProcedureInterruptedAtError,
    InvalidProcedureKindError,
    InvalidProcedureNameError,
    InvalidProcedureTruncateReasonError,
    InvalidStepKindError,
    ProcedureAlreadyExistsError,
    ProcedureAssetDecommissionedError,
    ProcedureCannotAbortError,
    ProcedureCannotCompleteError,
    ProcedureCannotStartError,
    ProcedureCannotTruncateError,
    ProcedureCapabilityExecutorMismatchError,
    ProcedureNotFoundError,
    ProcedureStepsLogbookClosedError,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import (
    abort_procedure,
    append_procedure_step,
    complete_procedure,
    get_procedure,
    list_procedures,
    register_procedure,
    start_procedure,
    truncate_procedure,
)
from cora.recipe.aggregates.capability import CapabilityNotFoundError


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error.

    Covers Invalid<X>NameError / Invalid<X>KindError /
    Invalid<X>AbortReasonError. All map to HTTP 400 +
    `{"detail": str(exc)}` body. Adding a new validation-style error
    is one extra entry in the tuple in `register_operation_routes`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    reason = exc.reason if isinstance(exc, UnauthorizedError) else str(exc)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": reason},
    )


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    """Shared 404 handler for every aggregate's NotFoundError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler for every aggregate's AlreadyExistsError.

    The decider raises these if the target stream already has events.
    In production with UUIDv7 ids this is essentially impossible, but
    the unmapped raise would surface as 500 instead of a clean 409 --
    this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for every transition-guard error.

    Covers ProcedureCannotStart / ProcedureCannotComplete /
    ProcedureCannotAbort / ProcedureCannotTruncate (FSM source-state
    guards), ProcedureAssetDecommissioned (cross-aggregate precondition
    guard at start_procedure), AND ProcedureStepsLogbookClosed (logbook
    write guard for non-Running Procedures). All map to HTTP 409 +
    `{"detail": str(exc)}`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_operation_routes(app: FastAPI) -> None:
    """Attach Operation slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_procedure.router)
    app.include_router(start_procedure.router)
    app.include_router(complete_procedure.router)
    app.include_router(abort_procedure.router)
    app.include_router(truncate_procedure.router)
    app.include_router(append_procedure_step.router)
    app.include_router(get_procedure.router)
    app.include_router(list_procedures.router)
    for validation_cls in (
        InvalidProcedureNameError,
        InvalidProcedureKindError,
        InvalidProcedureAbortReasonError,
        InvalidProcedureTruncateReasonError,
        InvalidProcedureInterruptedAtError,
        InvalidStepKindError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (
        ProcedureNotFoundError,
        # Phase 10d cross-BC reference: Procedure.capability_id points
        # at a Capability stream that doesn't exist (loaded at handler
        # time per eventual-consistency stance).
        CapabilityNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (ProcedureAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        ProcedureCannotStartError,
        ProcedureCannotCompleteError,
        ProcedureCannotAbortError,
        ProcedureCannotTruncateError,
        ProcedureAssetDecommissionedError,
        ProcedureStepsLogbookClosedError,
        # Phase 10d cross-BC guard: Procedure binds to a Capability whose
        # executor_shapes does not include Procedure.
        ProcedureCapabilityExecutorMismatchError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
