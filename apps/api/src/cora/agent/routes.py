"""HTTP setup for the Agent BC.

`register_agent_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots); Agent does not
re-register them.

## Loop-collapse pattern

Agent owns one aggregate. Four error families share response
shapes and get collapsed via the established Trust / Equipment /
Supply / Safety / Caution loop pattern:

  - 400 (validation): all `Invalid<X>` errors
  - 404 (load miss): AgentNotFound
  - 409 (defensive guard for AlreadyExists): AgentAlreadyExists
  - 409 (transition guards): AgentCannotVersion, AgentCannotDeprecate
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.agent.aggregates.agent import (
    AgentAlreadyExistsError,
    AgentCannotDeprecateError,
    AgentCannotVersionError,
    AgentNotFoundError,
    InvalidAgentCanonicalURIError,
    InvalidAgentCapabilitiesError,
    InvalidAgentCapabilityError,
    InvalidAgentDeprecationReasonError,
    InvalidAgentDescriptionError,
    InvalidAgentKindError,
    InvalidAgentNameError,
    InvalidAgentVersionError,
    InvalidModelRefError,
)
from cora.agent.errors import UnauthorizedError
from cora.agent.features import (
    define_agent,
    deprecate_agent,
    get_agent,
    version_agent,
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

    With UUIDv7 ids this is essentially impossible in production, but
    the unmapped raise would surface as 500 instead of a clean 409.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    Covers the `AgentCannot<Verb>Error` family: Version + Deprecate.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_agent_routes(app: FastAPI) -> None:
    """Attach Agent slice routers and exception handlers to the FastAPI app."""
    app.include_router(define_agent.router)
    app.include_router(version_agent.router)
    app.include_router(deprecate_agent.router)
    app.include_router(get_agent.router)
    for validation_cls in (
        InvalidAgentKindError,
        InvalidAgentNameError,
        InvalidAgentDescriptionError,
        InvalidAgentVersionError,
        InvalidAgentCanonicalURIError,
        InvalidAgentCapabilityError,
        InvalidAgentCapabilitiesError,
        InvalidAgentDeprecationReasonError,
        InvalidModelRefError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (AgentNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (AgentAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        AgentCannotVersionError,
        AgentCannotDeprecateError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
