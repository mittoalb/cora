"""HTTP setup for the Safety BC.

`register_safety_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to avoid
nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots). They produce the same
JSON shape regardless of which BC raised them, so Safety does not
re-register them.

## Loop-collapse pattern

Safety owns one aggregate (Clearance) at 11a-a. Validation errors
share the same response shape and get collapsed via the
Trust / Equipment / Supply-style loop pattern:

  - 400 (validation): Invalid<X> family (Title, Bindings,
    ValidityWindow, ExternalBinding, MitigationRef, HazardNotes,
    ExternalId)
  - 404 (load miss): ClearanceNotFound (raised by future update
    handlers in 11a-b/c; defensive registration today)
  - 409 (defensive guard for AlreadyExists): ClearanceAlreadyExists

11a-b will add the cannot-transition error family; 11a-c will add
expire + amend variants. Each sub-phase extends the loop tuples by
the new error classes.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.safety.aggregates.clearance import (
    ClearanceAlreadyExistsError,
    ClearanceNotFoundError,
    InvalidClearanceBindingsError,
    InvalidClearanceDeclarationTargetError,
    InvalidClearanceExternalBindingError,
    InvalidClearanceExternalIdError,
    InvalidClearanceHazardNotesError,
    InvalidClearanceMitigationRefError,
    InvalidClearanceTitleError,
    InvalidClearanceValidityWindowError,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features import (
    get_clearance,
    register_clearance,
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
    the unmapped raise would surface as 500 instead of a clean 409;
    this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_safety_routes(app: FastAPI) -> None:
    """Attach Safety slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_clearance.router)
    app.include_router(get_clearance.router)
    for validation_cls in (
        InvalidClearanceTitleError,
        InvalidClearanceBindingsError,
        InvalidClearanceDeclarationTargetError,
        InvalidClearanceValidityWindowError,
        InvalidClearanceExternalBindingError,
        InvalidClearanceMitigationRefError,
        InvalidClearanceHazardNotesError,
        InvalidClearanceExternalIdError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (ClearanceNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (ClearanceAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
