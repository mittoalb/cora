"""HTTP setup for the Equipment BC.

`register_equipment_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError` and `ConcurrencyError` are infra-layer
errors registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Equipment
does not re-register them.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.equipment.aggregates.capability import (
    CapabilityAlreadyExistsError,
    CapabilityNotFoundError,
    InvalidCapabilityNameError,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features import define_capability, get_capability


async def _handle_invalid_capability_name(request: Request, exc: Exception) -> JSONResponse:
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


async def _handle_capability_not_found(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_capability_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive guard: define_capability's decider raises this if the
    target stream already has events. In production with UUIDv7 ids
    this is essentially impossible, but the unmapped raise would
    surface as 500 instead of a clean 409 — this handler closes that
    gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_equipment_routes(app: FastAPI) -> None:
    """Attach Equipment slice routers and exception handlers to the FastAPI app."""
    app.include_router(define_capability.router)
    app.include_router(get_capability.router)
    app.add_exception_handler(InvalidCapabilityNameError, _handle_invalid_capability_name)
    app.add_exception_handler(CapabilityNotFoundError, _handle_capability_not_found)
    app.add_exception_handler(CapabilityAlreadyExistsError, _handle_capability_already_exists)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
