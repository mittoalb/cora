"""HTTP setup for the Campaign BC.

`register_campaign_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots); Campaign does not
re-register them.

## Loop-collapse pattern

Campaign owns one aggregate. Four error families share response
shapes and get collapsed via the Trust / Equipment / Supply / Safety
/ Caution loop pattern:

  - 400 (validation): InvalidCampaignName, InvalidCampaignDescription,
    InvalidCampaignTag, InvalidCampaignHoldReason,
    InvalidCampaignAbandonReason, InvalidCampaignExternalId
  - 404 (load miss): CampaignNotFound
  - 409 (defensive guard for AlreadyExists): CampaignAlreadyExists
  - 409 (transition guards): CampaignCannotStart, CampaignCannotHold,
    CampaignCannotResume, CampaignCannotClose, CampaignCannotAbandon
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.campaign.aggregates.campaign import (
    CampaignAlreadyExistsError,
    CampaignCannotAbandonError,
    CampaignCannotCloseError,
    CampaignCannotHoldError,
    CampaignCannotResumeError,
    CampaignCannotStartError,
    CampaignNotFoundError,
    InvalidCampaignAbandonReasonError,
    InvalidCampaignDescriptionError,
    InvalidCampaignExternalIdError,
    InvalidCampaignHoldReasonError,
    InvalidCampaignNameError,
    InvalidCampaignTagError,
)
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features import (
    abandon_campaign,
    close_campaign,
    get_campaign,
    hold_campaign,
    list_campaigns,
    register_campaign,
    resume_campaign,
    start_campaign,
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

    Covers the `CampaignCannot<Verb>Error` family: Start, Hold,
    Resume, Close, Abandon in 6i-a. Same pattern as Supply / Safety /
    Caution `_handle_cannot_transition`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_campaign_routes(app: FastAPI) -> None:
    """Attach Campaign slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_campaign.router)
    app.include_router(start_campaign.router)
    app.include_router(hold_campaign.router)
    app.include_router(resume_campaign.router)
    app.include_router(close_campaign.router)
    app.include_router(abandon_campaign.router)
    app.include_router(get_campaign.router)
    app.include_router(list_campaigns.router)
    for validation_cls in (
        InvalidCampaignNameError,
        InvalidCampaignDescriptionError,
        InvalidCampaignTagError,
        InvalidCampaignHoldReasonError,
        InvalidCampaignAbandonReasonError,
        InvalidCampaignExternalIdError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (CampaignNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (CampaignAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        CampaignCannotStartError,
        CampaignCannotHoldError,
        CampaignCannotResumeError,
        CampaignCannotCloseError,
        CampaignCannotAbandonError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
