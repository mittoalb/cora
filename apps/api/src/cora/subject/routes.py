"""HTTP setup for the Subject BC.

`register_subject_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError` and `ConcurrencyError` are infra-layer
errors registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Subject
does not re-register them.

Phase 4b adds two new domain errors via `mount_subject`:
`SubjectNotFoundError` (404) and `SubjectCannotMountError` (409).
Future transition slices (4c-4d) add their own `SubjectCannot<X>Error`
classes; each registers its own 409 handler. We deliberately don't
collapse via the Trust-style loop pattern yet — only one 404 + one
409 today; the loop pattern lands when 3+ such handlers exist.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.subject.aggregates.subject import (
    InvalidSubjectNameError,
    SubjectCannotMountError,
    SubjectNotFoundError,
)
from cora.subject.errors import UnauthorizedError
from cora.subject.features import mount_subject, register_subject


async def _handle_invalid_subject_name(request: Request, exc: Exception) -> JSONResponse:
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


async def _handle_subject_not_found(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_subject_cannot_mount(request: Request, exc: Exception) -> JSONResponse:
    """Subject in wrong state for mount transition. 409 Conflict."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_subject_routes(app: FastAPI) -> None:
    """Attach Subject slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_subject.router)
    app.include_router(mount_subject.router)
    app.add_exception_handler(InvalidSubjectNameError, _handle_invalid_subject_name)
    app.add_exception_handler(SubjectNotFoundError, _handle_subject_not_found)
    app.add_exception_handler(SubjectCannotMountError, _handle_subject_cannot_mount)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
