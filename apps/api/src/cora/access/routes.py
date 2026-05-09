"""HTTP setup for the Access BC.

`register_access_routes(app)` includes every slice's router and registers
exception handlers that translate the BC's domain / application / infra
errors to HTTP status codes. Called once at app construction (not in
lifespan) so routes are registered before the first request arrives.

JSONResponse is used (not HTTPException) per FastAPI guidance to avoid
nested-exception pitfalls.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.access.aggregates.actor import (
    ActorAlreadyDeactivatedError,
    ActorNotFoundError,
    InvalidActorNameError,
)
from cora.access.errors import UnauthorizedError
from cora.access.features import deactivate_actor, get_actor, register_actor
from cora.infrastructure.ports import ConcurrencyError, IdempotencyConflictError


async def _handle_invalid_actor_name(request: Request, exc: Exception) -> JSONResponse:
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


async def _handle_actor_not_found(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_deactivated(request: Request, exc: Exception) -> JSONResponse:
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


def register_access_routes(app: FastAPI) -> None:
    """Attach Access slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_actor.router)
    app.include_router(deactivate_actor.router)
    app.include_router(get_actor.router)
    app.add_exception_handler(InvalidActorNameError, _handle_invalid_actor_name)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
    app.add_exception_handler(ActorNotFoundError, _handle_actor_not_found)
    app.add_exception_handler(ActorAlreadyDeactivatedError, _handle_already_deactivated)
    app.add_exception_handler(ConcurrencyError, _handle_concurrency_conflict)
    app.add_exception_handler(IdempotencyConflictError, _handle_idempotency_conflict)
