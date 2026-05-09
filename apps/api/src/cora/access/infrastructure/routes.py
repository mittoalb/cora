"""HTTP surface for the Access BC.

Exposes `POST /actors`, the REST entrypoint for `RegisterActor`. The
route is a thin shell: pull the wired handler off `app.state.access`,
parse the body via Pydantic, supply correlation + invoker context, await
the handler, return the new id.

Cross-BC pattern (`register_<bc>_routes(app)`):
    - Each BC's infrastructure module exports a `register_<bc>_routes`
      that includes the BC's APIRouter and registers exception handlers
      that translate the BC's domain errors to HTTP status codes.
    - Called once at app construction (not in lifespan): routes must be
      registered before the first request, lifespan runs at startup.
    - Keeps `cora.api.main` free of per-BC import sprawl: one import
      and one call per BC, regardless of how many endpoints land.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID, uuid4

from asgi_correlation_id import correlation_id
from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from cora.access.application.register_actor import (
    RegisterActorHandler,
    UnauthorizedError,
)
from cora.access.domain.actor import InvalidActorNameError
from cora.access.domain.commands import RegisterActor

# Phase 1 bootstrap: every command runs as a "system" actor under
# AllowAllAuthorize. Phase 3 replaces this with the authenticated
# actor extracted from a header / token by the Trust BC.
_SYSTEM_ACTOR_ID = UUID("00000000-0000-0000-0000-000000000000")


class RegisterActorRequest(BaseModel):
    """Body for `POST /actors`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Display name for the new actor.",
    )


class RegisterActorResponse(BaseModel):
    """Response body for `POST /actors`."""

    actor_id: UUID


def _get_register_actor_handler(request: Request) -> RegisterActorHandler:
    handler: RegisterActorHandler = request.app.state.access.register_actor
    return handler


def _get_correlation_id() -> UUID:
    """Pull the request correlation id from the asgi-correlation-id contextvar.

    The middleware default generator emits `uuid4().hex` (32-char hex,
    no dashes) which `UUID(...)` accepts. Inbound `X-Request-ID` values
    that aren't valid UUIDs fall back to a fresh UUID4 so the handler
    contract (correlation_id: UUID) is always satisfied.
    """
    raw = correlation_id.get()
    if raw:
        try:
            return UUID(raw)
        except ValueError:
            pass
    return uuid4()


def _get_invoker_actor_id() -> UUID:
    """Resolve the invoker actor id. Phase 1: hardcoded system actor."""
    return _SYSTEM_ACTOR_ID


router = APIRouter(tags=["access"])


@router.post(
    "/actors",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterActorResponse,
    summary="Register a new actor",
)
async def post_actors(
    body: RegisterActorRequest,
    handler: Annotated[RegisterActorHandler, Depends(_get_register_actor_handler)],
    cid: Annotated[UUID, Depends(_get_correlation_id)],
    invoker_id: Annotated[UUID, Depends(_get_invoker_actor_id)],
) -> RegisterActorResponse:
    actor_id = await handler(
        RegisterActor(name=body.name),
        actor_id=invoker_id,
        correlation_id=cid,
    )
    return RegisterActorResponse(actor_id=actor_id)


# Exception handlers translate domain / application errors to HTTP
# responses. JSONResponse is used (not HTTPException) per FastAPI
# guidance to avoid nested-exception pitfalls.

ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


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
    """Attach Access routes and exception handlers to the FastAPI app."""
    app.include_router(router)
    app.add_exception_handler(InvalidActorNameError, _handle_invalid_actor_name)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
