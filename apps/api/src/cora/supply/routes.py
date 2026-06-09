"""HTTP setup for the Supply BC.

`register_supply_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots). They produce the
same JSON shape regardless of which BC raised them, so Supply does
not re-register them.

## Loop-collapse pattern

Supply owns one aggregate (Supply). Four error families share the
same response shape and get collapsed via the Trust /
Equipment-style loop pattern:

  - 400 (validation): InvalidSupplyName, InvalidSupplyKind,
    InvalidSupplyReason, InvalidFacilityCode (cross-BC VO; mapped
    here as the in-process safety net for defensive callers that
    bypass the route + tool Pydantic regex)
  - 404 (load + cross-BC miss): SupplyNotFound,
    SupplyFacilityNotFound, SupplyContainingAssetNotFound
  - 409 (defensive guard for AlreadyExists): SupplyAlreadyExists
  - 409 (transition guard): SupplyCannot{MarkAvailable, Degrade,
    MarkUnavailable, MarkRecovering, Restore, Deregister}

Adding a new aggregate (or a new transition error) becomes one tuple
entry per family. The cannot-transition tuple grew from 1 to 5
entries when 10a-b shipped the FSM-closure transitions, and to 6
when `deregister_supply` shipped the lifecycle-terminal transition.
The not-found tuple grew from 1 to 2 when Slice 7A added the
cross-BC Facility binding via `register_supply`, then to 3 when
Slice 7B added the cross-BC containing-Asset binding.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.shared.facility_code import InvalidFacilityCodeError
from cora.supply.aggregates.supply import (
    InvalidMonitorRefError,
    InvalidSupplyKindError,
    InvalidSupplyNameError,
    InvalidSupplyReasonError,
    MonitorTriggerNotPermittedError,
    SupplyAlreadyExistsError,
    SupplyCannotDegradeError,
    SupplyCannotDeregisterError,
    SupplyCannotMarkAvailableError,
    SupplyCannotMarkRecoveringError,
    SupplyCannotMarkUnavailableError,
    SupplyCannotRestoreError,
    SupplyContainingAssetNotFoundError,
    SupplyFacilityNotFoundError,
    SupplyNotFoundError,
)
from cora.supply.errors import UnauthorizedError
from cora.supply.features import (
    degrade_supply,
    deregister_supply,
    get_supply,
    list_supplies,
    mark_supply_available,
    mark_supply_recovering,
    mark_supply_unavailable,
    observe_supply_status,
    register_supply,
    restore_supply,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error.

    Covers Invalid<X>NameError / Invalid<X>KindError /
    Invalid<X>ReasonError VOs. All map to the same HTTP 400 +
    `{"detail": str(exc)}` body. Adding a new validation-style error
    is one extra entry in the tuple in `register_supply_routes`.
    """
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
    the unmapped raise would surface as 500 instead of a clean 409 —
    this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    Covers the `<X>Cannot<Verb>Error` family: Supply's MarkAvailable
    (10a-a), the FSM-closure quartet (Degrade / MarkUnavailable /
    MarkRecovering / Restore), and the lifecycle-terminal Deregister.
    Same pattern as Subject's / Equipment's `_handle_cannot_transition`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_supply_routes(app: FastAPI) -> None:
    """Attach Supply slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_supply.router)
    app.include_router(mark_supply_available.router)
    app.include_router(degrade_supply.router)
    app.include_router(mark_supply_unavailable.router)
    app.include_router(mark_supply_recovering.router)
    app.include_router(restore_supply.router)
    app.include_router(deregister_supply.router)
    # observe_supply_status: in-process-only per
    # [[project_supply_monitor_trigger_design]]. The included router
    # is empty (no endpoints registered); inclusion satisfies the
    # routes-completeness architecture fitness without exposing a
    # public HTTP surface.
    app.include_router(observe_supply_status.router)
    app.include_router(get_supply.router)
    app.include_router(list_supplies.router)
    for validation_cls in (
        InvalidSupplyNameError,
        InvalidSupplyKindError,
        InvalidSupplyReasonError,
        InvalidMonitorRefError,
        MonitorTriggerNotPermittedError,
        InvalidFacilityCodeError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (
        SupplyNotFoundError,
        SupplyFacilityNotFoundError,
        SupplyContainingAssetNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (SupplyAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        SupplyCannotMarkAvailableError,
        SupplyCannotDegradeError,
        SupplyCannotMarkUnavailableError,
        SupplyCannotMarkRecoveringError,
        SupplyCannotRestoreError,
        SupplyCannotDeregisterError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
