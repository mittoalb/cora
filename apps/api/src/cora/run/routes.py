"""HTTP setup for the Run BC.

`register_run_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError` and `ConcurrencyError` are infra-layer
errors registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Run
does not re-register them.

## Loop-collapse pattern

Mirrors Recipe / Equipment / Subject. Generic error handlers per
family, tuple loops to register them. Phase 6f-2 adds the two
transition handlers + their guard errors.

  - 400 (validation): InvalidRunNameError, InvalidRunAbortReasonError
  - 404 (load miss): RunNotFoundError
  - 409 (defensive guard for AlreadyExists): RunAlreadyExistsError
  - 409 (Run-start binding-state guards): PlanDeprecatedError,
    SubjectNotMountableError, RunAssetDecommissionedError,
    RunCapabilitiesNotSatisfiedError
  - 409 (Run transition guards, 6f-2): RunCannotCompleteError,
    RunCannotAbortError
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.run.aggregates.run import (
    InvalidRunAbortReasonError,
    InvalidRunNameError,
    PlanDeprecatedError,
    RunAlreadyExistsError,
    RunAssetDecommissionedError,
    RunCannotAbortError,
    RunCannotCompleteError,
    RunCapabilitiesNotSatisfiedError,
    RunNotFoundError,
    SubjectNotMountableError,
)
from cora.run.errors import UnauthorizedError
from cora.run.features import abort_run, complete_run, get_run, start_run


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error."""
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
    """Shared 404 handler for the aggregate's NotFoundError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler for RunAlreadyExistsError.

    The decider raises this if the target stream already has events.
    In production with UUIDv7 ids this is essentially impossible, but
    the unmapped raise would surface as 500 instead of a clean 409.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for binding-state and transition guards.

    Covers Run-start binding-state guards (Plan deprecated, Subject
    not mountable, Asset decommissioned, capabilities not satisfied)
    plus Run transition guards (cannot complete / cannot abort).
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_run_routes(app: FastAPI) -> None:
    """Attach Run slice routers and exception handlers to the FastAPI app."""
    app.include_router(start_run.router)
    app.include_router(complete_run.router)
    app.include_router(abort_run.router)
    app.include_router(get_run.router)
    for validation_cls in (InvalidRunNameError, InvalidRunAbortReasonError):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (RunNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (RunAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        # Run-start binding-state guards.
        PlanDeprecatedError,
        SubjectNotMountableError,
        RunAssetDecommissionedError,
        RunCapabilitiesNotSatisfiedError,
        # Run transition guards (6f-2).
        RunCannotCompleteError,
        RunCannotAbortError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
