"""HTTP setup for the Caution BC.

`register_caution_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots); Caution does not
re-register them.

## Loop-collapse pattern

Caution owns one aggregate. Four error families share response
shapes and get collapsed via the Trust / Equipment / Supply / Safety
loop pattern:

  - 400 (validation): InvalidCautionText, InvalidCautionWorkaround,
    InvalidCautionTag, InvalidCautionExpiresAt,
    InvalidCautionSupersedeTarget
  - 404 (load miss): CautionNotFound
  - 409 (defensive guard for AlreadyExists): CautionAlreadyExists
  - 409 (transition guards): CautionCannotSupersede,
    CautionCannotRetire
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.caution.aggregates.caution import (
    CautionAlreadyExistsError,
    CautionCannotRetireError,
    CautionCannotSupersedeError,
    CautionNotFoundError,
    InvalidCautionExpiresAtError,
    InvalidCautionSupersedeTargetError,
    InvalidCautionTagError,
    InvalidCautionTextError,
    InvalidCautionWorkaroundError,
)
from cora.caution.errors import UnauthorizedError
from cora.caution.features import (
    get_caution,
    list_cautions,
    register_caution,
    retire_caution,
    supersede_caution,
)


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
    the unmapped raise would surface as 500 instead of a clean 409.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    Covers the `CautionCannot<Verb>Error` family: Supersede and Retire
    in 11b-a. Same pattern as Supply / Safety `_handle_cannot_transition`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_caution_routes(app: FastAPI) -> None:
    """Attach Caution slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_caution.router)
    app.include_router(supersede_caution.router)
    app.include_router(retire_caution.router)
    app.include_router(get_caution.router)
    app.include_router(list_cautions.router)
    for validation_cls in (
        InvalidCautionTextError,
        InvalidCautionWorkaroundError,
        InvalidCautionTagError,
        InvalidCautionExpiresAtError,
        InvalidCautionSupersedeTargetError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (CautionNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (CautionAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        CautionCannotSupersedeError,
        CautionCannotRetireError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
