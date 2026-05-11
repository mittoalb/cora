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

## Loop-collapse pattern

Equipment owns multiple aggregates (Capability + Asset, with more
slices to come). Three error families share the same response
shape and get collapsed via Trust's `_handle_invalid_name`-style
loop pattern:

  - 400 (validation): InvalidCapabilityName, InvalidAssetName,
    InvalidAssetParent
  - 404 (load miss): CapabilityNotFound, AssetNotFound
  - 409 (defensive guard for AlreadyExists): CapabilityAlreadyExists,
    AssetAlreadyExists

Adding a new aggregate (or a new transition error) becomes one tuple
entry per family. When the SubjectCannot<X>Error family lands for
Asset lifecycle (5c+), it gets its own loop following Subject's
precedent.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.equipment.aggregates.asset import (
    AssetAlreadyExistsError,
    AssetCannotActivateError,
    AssetCannotAddCapabilityError,
    AssetCannotDecommissionError,
    AssetCannotEnterMaintenanceError,
    AssetCannotRelocateError,
    AssetCannotRemoveCapabilityError,
    AssetCannotRestoreFromMaintenanceError,
    AssetNotFoundError,
    InvalidAssetNameError,
    InvalidAssetParentError,
)
from cora.equipment.aggregates.capability import (
    CapabilityAlreadyExistsError,
    CapabilityNotFoundError,
    InvalidCapabilityNameError,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features import (
    activate_asset,
    add_asset_capability,
    decommission_asset,
    define_capability,
    enter_maintenance,
    get_asset,
    get_capability,
    register_asset,
    relocate_asset,
    remove_asset_capability,
    restore_from_maintenance,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error.

    Covers Invalid<X>NameError VOs and InvalidAssetParentError. All
    map to the same HTTP 400 + `{"detail": str(exc)}` body. Adding
    a new validation-style error is one extra entry in the tuple in
    `register_equipment_routes`.
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

    The decider raises these if the target stream already has
    events. In production with UUIDv7 ids this is essentially
    impossible, but the unmapped raise would surface as 500 instead
    of a clean 409 — this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    Covers the `<X>Cannot<Verb>Error` family (Asset's Activate /
    Decommission in 5c; future Maintenance / Restore in 5e). Same
    pattern as Subject's `_handle_cannot_transition`.
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
    app.include_router(register_asset.router)
    app.include_router(activate_asset.router)
    app.include_router(decommission_asset.router)
    app.include_router(relocate_asset.router)
    app.include_router(enter_maintenance.router)
    app.include_router(restore_from_maintenance.router)
    app.include_router(add_asset_capability.router)
    app.include_router(remove_asset_capability.router)
    app.include_router(get_asset.router)
    for validation_cls in (
        InvalidCapabilityNameError,
        InvalidAssetNameError,
        InvalidAssetParentError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (CapabilityNotFoundError, AssetNotFoundError):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (CapabilityAlreadyExistsError, AssetAlreadyExistsError):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        AssetCannotActivateError,
        AssetCannotDecommissionError,
        AssetCannotRelocateError,
        AssetCannotEnterMaintenanceError,
        AssetCannotRestoreFromMaintenanceError,
        AssetCannotAddCapabilityError,
        AssetCannotRemoveCapabilityError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
