"""HTTP setup for the Federation BC.

`register_federation_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

Stage 2b attaches the five Permit lifecycle slice routers
(`register_permit` + `activate_permit` + `suspend_permit` +
`resume_permit` + `revoke_permit`). Stage 2c-credential attaches
the five Credential lifecycle slice routers (`register_credential`
+ `start_credential_rotation` + `complete_credential_rotation` +
`abort_credential_rotation` + `revoke_credential`). Stage 2c-seal
attaches the five Seal lifecycle slice routers (`initialize_seal`
+ `sign_seal_pointer` + `rotate_seal_online_key` +
`start_seal_republishing` + `complete_seal_republishing`). The
Seal domain-error handlers were wired alongside the Credential
slices, so the arch-fitness
`test_every_domain_error_registered_as_http_handler` passed
day-one.
"""

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.federation.aggregates.credential.state import (
    CredentialAlreadyExistsError,
    CredentialCannotRevokeError,
    CredentialCannotRotateError,
    CredentialExpiredError,
    CredentialNotFoundError,
    InvalidCredentialSecretRefError,
)
from cora.federation.aggregates.permit.state import (
    InvalidPermitScopeError,
    PermitAlreadyExistsError,
    PermitCannotActivateError,
    PermitCannotResumeError,
    PermitCannotRevokeError,
    PermitCannotSuspendError,
    PermitNotFoundError,
    PermitScopeCollapseError,
    UnsupportedCanonicalizationVersionError,
)
from cora.federation.aggregates.seal.state import (
    SealAlreadyExistsError,
    SealCannotCompleteRepublishingError,
    SealCannotRotateError,
    SealCannotSignError,
    SealCannotStartRepublishingError,
    SealKeyCollisionError,
    SealKeyPurposeMismatchError,
    SealNotFoundError,
    SealSequenceNumberRegressionError,
)
from cora.federation.errors import FederationError, UnauthorizedError
from cora.federation.features import (
    abort_credential_rotation,
    activate_permit,
    complete_credential_rotation,
    complete_seal_republishing,
    initialize_seal,
    register_credential,
    register_permit,
    resume_permit,
    revoke_credential,
    revoke_permit,
    rotate_seal_online_key,
    sign_seal_pointer,
    start_credential_rotation,
    start_seal_republishing,
    suspend_permit,
)

federation_router = APIRouter(prefix="/federation", tags=["federation"])


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_unprocessable_error(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
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


async def _handle_conflict(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    reason = exc.reason if isinstance(exc, UnauthorizedError) else str(exc)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": reason},
    )


async def _handle_federation_error(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


def register_federation_routes(app: FastAPI) -> None:
    """Attach Federation slice routers and exception handlers to the FastAPI app."""
    app.include_router(federation_router)
    app.include_router(register_permit.router)
    app.include_router(activate_permit.router)
    app.include_router(suspend_permit.router)
    app.include_router(resume_permit.router)
    app.include_router(revoke_permit.router)
    app.include_router(register_credential.router)
    app.include_router(start_credential_rotation.router)
    app.include_router(complete_credential_rotation.router)
    app.include_router(abort_credential_rotation.router)
    app.include_router(revoke_credential.router)
    app.include_router(initialize_seal.router)
    app.include_router(sign_seal_pointer.router)
    app.include_router(rotate_seal_online_key.router)
    app.include_router(start_seal_republishing.router)
    app.include_router(complete_seal_republishing.router)
    for validation_cls in (
        InvalidPermitScopeError,
        InvalidCredentialSecretRefError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for unprocessable_cls in (
        PermitScopeCollapseError,
        UnsupportedCanonicalizationVersionError,
        CredentialExpiredError,
        SealKeyCollisionError,
        SealKeyPurposeMismatchError,
        SealSequenceNumberRegressionError,
    ):
        app.add_exception_handler(unprocessable_cls, _handle_unprocessable_error)
    for not_found_cls in (
        PermitNotFoundError,
        CredentialNotFoundError,
        SealNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (
        PermitAlreadyExistsError,
        CredentialAlreadyExistsError,
        SealAlreadyExistsError,
    ):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for conflict_cls in (
        PermitCannotActivateError,
        PermitCannotSuspendError,
        PermitCannotResumeError,
        PermitCannotRevokeError,
        CredentialCannotRotateError,
        CredentialCannotRevokeError,
        SealCannotSignError,
        SealCannotRotateError,
        SealCannotStartRepublishingError,
        SealCannotCompleteRepublishingError,
    ):
        app.add_exception_handler(conflict_cls, _handle_conflict)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
    app.add_exception_handler(FederationError, _handle_federation_error)


__all__ = ["federation_router", "register_federation_routes"]
