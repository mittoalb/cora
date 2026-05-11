"""HTTP setup for the Recipe BC.

`register_recipe_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError` and `ConcurrencyError` are infra-layer
errors registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Recipe
does not re-register them.

## Loop-collapse pattern

Mirrors Equipment / Subject. Generic error handlers per family,
tuple loops to register them. Phase 6a only ships Method, so the
tuples are single-element today; future aggregates (Practice / Plan
/ Run) and transition errors append entries without restructuring.

  - 400 (validation): InvalidMethodNameError
  - 404 (load miss): MethodNotFoundError
  - 409 (defensive guard for AlreadyExists): MethodAlreadyExistsError
  - 409 (transition guards): future <Aggregate>Cannot<Verb>Error families
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.recipe.aggregates.method import (
    InvalidMethodNameError,
    MethodAlreadyExistsError,
    MethodNotFoundError,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features import (
    define_method,
    get_method,
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
    the unmapped raise would surface as 500 instead of a clean 409 —
    this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_recipe_routes(app: FastAPI) -> None:
    """Attach Recipe slice routers and exception handlers to the FastAPI app."""
    app.include_router(define_method.router)
    app.include_router(get_method.router)
    for validation_cls in (InvalidMethodNameError,):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (MethodNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (MethodAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
