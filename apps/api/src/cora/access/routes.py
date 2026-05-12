"""HTTP setup for the Access BC.

`register_access_routes(app)` includes every slice's router and registers
exception handlers that translate the BC's domain / application / infra
errors to HTTP status codes. Called once at app construction (not in
lifespan) so routes are registered before the first request arrives.

JSONResponse is used (not HTTPException) per FastAPI guidance to avoid
nested-exception pitfalls.

## Loop-collapse pattern (cross-BC normalization)

Each error family that maps to one HTTP status code with the same
`{"detail": str(exc)}` body shares one generic handler, registered
against a tuple of error classes via a loop. Adding a new error in
a family is one tuple entry — no new handler function. Mirrors the
shape Equipment + Subject use; Access (the oldest BC) was normalized
in the post-5b cleanup so all 4 BCs follow the same pattern.

## Cross-BC infra errors registered here

`ConcurrencyError` and `IdempotencyConflictError` are infrastructure-
layer errors that any BC can raise. Access (the first BC that boots)
registers them globally — Subject / Trust / Equipment do NOT
re-register them. The JSON shape is the same regardless of which BC
issued the error.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.access.aggregates.actor import (
    ActorAlreadyDeactivatedError,
    ActorAlreadyExistsError,
    ActorNotFoundError,
    InvalidActorNameError,
)
from cora.access.errors import UnauthorizedError
from cora.access.features import (
    deactivate_actor,
    get_actor,
    list_actors,
    register_actor,
)
from cora.infrastructure.ports import ConcurrencyError, IdempotencyConflictError
from cora.infrastructure.projection import InvalidCursorError


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error (Invalid<X>...)."""
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

    The decider raises these if the target stream already has
    events. In production with UUIDv7 ids this is essentially
    impossible, but the unmapped raise would surface as 500 instead
    of a clean 409 — this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    Covers Subject's `<Bc>Cannot<Verb>Error` family (the locked
    naming convention) and Access's legacy `ActorAlreadyDeactivatedError`
    outlier. Both block a state transition; both return the same
    JSON shape. (Outlier rename to `ActorCannotDeactivateError` is
    deferred until Access grows a 2nd state-transition guard.)
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_concurrency_conflict(request: Request, exc: Exception) -> JSONResponse:
    """Optimistic-concurrency loser. The caller can retry with a fresh load."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_idempotency_conflict(request: Request, exc: Exception) -> JSONResponse:
    """Same Idempotency-Key reused with a different command body — client bug."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


async def _handle_invalid_cursor(request: Request, exc: Exception) -> JSONResponse:
    """Malformed pagination cursor — client passed a corrupt /
    truncated / hand-crafted cursor instead of one from a previous
    response's `next_cursor` field."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


def register_access_routes(app: FastAPI) -> None:
    """Attach Access slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_actor.router)
    app.include_router(deactivate_actor.router)
    app.include_router(get_actor.router)
    app.include_router(list_actors.router)
    for validation_cls in (InvalidActorNameError,):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (ActorNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (ActorAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (ActorAlreadyDeactivatedError,):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
    # Infrastructure errors (cross-BC; Access registers them globally — see module docstring).
    app.add_exception_handler(ConcurrencyError, _handle_concurrency_conflict)
    app.add_exception_handler(IdempotencyConflictError, _handle_idempotency_conflict)
    app.add_exception_handler(InvalidCursorError, _handle_invalid_cursor)
