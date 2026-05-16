"""HTTP setup for the Decision BC.

`register_decision_routes(app)` includes every slice's router and
registers exception handlers translating domain / application
errors to HTTP status codes.

  - 400 (validation): Invalid<X>...Error family + OverrideKindRequiresParentError
  - 404: DecisionNotFoundError
  - 409 (defensive AlreadyExists): DecisionAlreadyExistsError
  - 409 (cross-aggregate refs): DeciderActorMissingError, ParentDecisionMissingError

## Cross-BC infra errors NOT registered here

`ConcurrencyError`, `IdempotencyConflictError`,
`IdempotencyClaimLostError`, `CachedHandlerError`, and
`InvalidCursorError` are infrastructure-layer errors that any BC
can raise. They're registered globally in `cora/access/routes.py`
(the first BC that boots); other BCs do NOT re-register them. The
JSON shape is the same regardless of which BC issued the error.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.decision.aggregates.decision import (
    DeciderActorMissingError,
    DecisionAlreadyExistsError,
    DecisionLogbookAlreadyOpenError,
    DecisionLogbookNotOpenError,
    DecisionNotFoundError,
    InvalidDecisionAlternativesError,
    InvalidDecisionChoiceError,
    InvalidDecisionConfidenceError,
    InvalidDecisionContextError,
    InvalidDecisionInputsError,
    InvalidDecisionReasoningError,
    InvalidDecisionRuleError,
    InvalidReasoningSignatureError,
    ParentDecisionMissingError,
)
from cora.decision.errors import OverrideKindRequiresParentError, UnauthorizedError
from cora.decision.features import (
    append_reasoning_entry,
    get_decision,
    list_decisions,
    register_decision,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
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
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cross_agg_conflict(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for cross-aggregate-reference errors."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_decision_routes(app: FastAPI) -> None:
    """Attach Decision slice routers and exception handlers."""
    app.include_router(register_decision.router)
    app.include_router(get_decision.router)
    app.include_router(append_reasoning_entry.router)
    app.include_router(list_decisions.router)
    for validation_cls in (
        InvalidDecisionChoiceError,
        InvalidDecisionContextError,
        InvalidDecisionReasoningError,
        InvalidDecisionRuleError,
        InvalidDecisionConfidenceError,
        InvalidDecisionAlternativesError,
        InvalidDecisionInputsError,
        InvalidReasoningSignatureError,
        OverrideKindRequiresParentError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (DecisionNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (DecisionAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cross_agg_cls in (DeciderActorMissingError, ParentDecisionMissingError):
        app.add_exception_handler(cross_agg_cls, _handle_cross_agg_conflict)
    # Logbook-state transition guards (at-most-one-open + close-only-when-open
    # invariants from the Decision logbook aggregate); 409 shape mirrors the
    # cross-agg-conflict family.
    for logbook_state_cls in (
        DecisionLogbookAlreadyOpenError,
        DecisionLogbookNotOpenError,
    ):
        app.add_exception_handler(logbook_state_cls, _handle_cross_agg_conflict)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
