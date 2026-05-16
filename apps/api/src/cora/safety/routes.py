"""HTTP setup for the Safety BC.

`register_safety_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes.

11a-b adds 6 transition-slice routers + 7 cannot-* error handlers
(the FSM-closure cannot-* family) + 3 invalid-* error handlers
(reviewer-role / reviewer-notes / reject-reason / review-step-index).
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.safety.aggregates.clearance import (
    ClearanceAlreadyExistsError,
    ClearanceCannotActivateError,
    ClearanceCannotAppendReviewStepError,
    ClearanceCannotApproveError,
    ClearanceCannotRejectError,
    ClearanceCannotStartReviewError,
    ClearanceCannotSubmitError,
    ClearanceNotFoundError,
    InvalidClearanceBindingsError,
    InvalidClearanceDeclarationTargetError,
    InvalidClearanceExternalBindingError,
    InvalidClearanceExternalIdError,
    InvalidClearanceHazardNotesError,
    InvalidClearanceMitigationRefError,
    InvalidClearanceRejectReasonError,
    InvalidClearanceReviewerNotesError,
    InvalidClearanceReviewerRoleError,
    InvalidClearanceReviewStepIndexError,
    InvalidClearanceTitleError,
    InvalidClearanceValidityWindowError,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features import (
    activate_clearance,
    append_clearance_review_step,
    approve_clearance,
    get_clearance,
    list_clearances,
    register_clearance,
    reject_clearance,
    start_review_clearance,
    submit_clearance,
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
    """Defensive 409 handler for every aggregate's AlreadyExistsError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    Covers the `Clearance.Cannot<Verb>Error` family: 11a-b's FSM-closure
    sextet (Submit / StartReview / AppendReviewStep / Approve / Reject /
    Activate). Same pattern as Supply / Operation `_handle_cannot_transition`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_safety_routes(app: FastAPI) -> None:
    """Attach Safety slice routers and exception handlers to the FastAPI app."""
    # 11a-a slices
    app.include_router(register_clearance.router)
    app.include_router(get_clearance.router)
    # 11a-b transition slices
    app.include_router(submit_clearance.router)
    app.include_router(start_review_clearance.router)
    app.include_router(append_clearance_review_step.router)
    app.include_router(approve_clearance.router)
    app.include_router(reject_clearance.router)
    app.include_router(activate_clearance.router)
    # 11a-b list endpoint
    app.include_router(list_clearances.router)
    for validation_cls in (
        InvalidClearanceTitleError,
        InvalidClearanceBindingsError,
        InvalidClearanceDeclarationTargetError,
        InvalidClearanceValidityWindowError,
        InvalidClearanceExternalBindingError,
        InvalidClearanceMitigationRefError,
        InvalidClearanceHazardNotesError,
        InvalidClearanceExternalIdError,
        InvalidClearanceReviewerRoleError,
        InvalidClearanceReviewerNotesError,
        InvalidClearanceReviewStepIndexError,
        InvalidClearanceRejectReasonError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (ClearanceNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (ClearanceAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        ClearanceCannotSubmitError,
        ClearanceCannotStartReviewError,
        ClearanceCannotAppendReviewStepError,
        ClearanceCannotApproveError,
        ClearanceCannotRejectError,
        ClearanceCannotActivateError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
