"""HTTP setup for the Access BC.

`register_access_routes(app)` includes every slice's router and registers
exception handlers that translate the BC's domain / application errors
to HTTP status codes. Called once at app construction (not in lifespan)
so routes are registered before the first request arrives.

JSONResponse is used (not HTTPException) per FastAPI guidance to avoid
nested-exception pitfalls.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.access.aggregates.actor import InvalidActorNameError
from cora.access.features import register_actor
from cora.access.features.register_actor import UnauthorizedError


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


def register_access_routes(app: FastAPI) -> None:
    """Attach Access slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_actor.router)
    app.add_exception_handler(InvalidActorNameError, _handle_invalid_actor_name)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
