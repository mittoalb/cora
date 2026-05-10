"""HTTP setup for the Trust BC.

`register_trust_routes(app)` includes every slice's router and registers
exception handlers that translate the BC's domain / application errors
to HTTP status codes. Called once at app construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to avoid
nested-exception pitfalls.

`IdempotencyConflictError` and `ConcurrencyError` are infra-layer
errors registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Trust does
not re-register them. A `ZoneNotFoundError` (or analogous "missing
target" handler) lands here once the first slice that loads-and-folds
the Zone stream ships (3b+); per YAGNI it doesn't exist yet.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.trust.aggregates.conduit import InvalidConduitNameError
from cora.trust.aggregates.policy import InvalidPolicyNameError
from cora.trust.aggregates.zone import InvalidZoneNameError
from cora.trust.errors import UnauthorizedError
from cora.trust.features import define_conduit, define_policy, define_zone


async def _handle_invalid_zone_name(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_invalid_conduit_name(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_invalid_policy_name(request: Request, exc: Exception) -> JSONResponse:
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


def register_trust_routes(app: FastAPI) -> None:
    """Attach Trust slice routers and exception handlers to the FastAPI app."""
    app.include_router(define_zone.router)
    app.include_router(define_conduit.router)
    app.include_router(define_policy.router)
    app.add_exception_handler(InvalidZoneNameError, _handle_invalid_zone_name)
    app.add_exception_handler(InvalidConduitNameError, _handle_invalid_conduit_name)
    app.add_exception_handler(InvalidPolicyNameError, _handle_invalid_policy_name)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
