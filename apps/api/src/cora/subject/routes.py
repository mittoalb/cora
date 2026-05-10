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

Phase 4b-c add a growing family of `SubjectCannot<X>Error` classes
(one per transition: Mount, Measure, Remove). All three map to the
same HTTP 409 + `{"detail": str}` body, so we collapse them via the
Trust-style loop pattern (`_handle_subject_cannot_transition`
registered against all three classes). Adding a fourth in 4d
(SubjectCannotReturn / Store / Discard) is one extra entry in the
tuple. The Mount-only handler from 4b is removed; net behavior is
unchanged because the shared handler produces the same response shape.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.subject.aggregates.subject import (
    InvalidSubjectNameError,
    SubjectCannotMeasureError,
    SubjectCannotMountError,
    SubjectCannotRemoveError,
    SubjectNotFoundError,
)
from cora.subject.errors import UnauthorizedError
from cora.subject.features import (
    measure_subject,
    mount_subject,
    register_subject,
    remove_subject,
)


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


async def _handle_subject_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for every `SubjectCannot<X>Error`.

    All transition-state-mismatch errors map to the same HTTP 409 +
    `{"detail": str(exc)}` body. One handler registered against
    multiple exception classes via a loop in `register_subject_routes`
    — adding a new transition in 4d is one extra entry in the tuple.
    Mirrors Trust BC's `_handle_invalid_name` collapse pattern.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_subject_routes(app: FastAPI) -> None:
    """Attach Subject slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_subject.router)
    app.include_router(mount_subject.router)
    app.include_router(measure_subject.router)
    app.include_router(remove_subject.router)
    app.add_exception_handler(InvalidSubjectNameError, _handle_invalid_subject_name)
    app.add_exception_handler(SubjectNotFoundError, _handle_subject_not_found)
    for cannot_transition_cls in (
        SubjectCannotMountError,
        SubjectCannotMeasureError,
        SubjectCannotRemoveError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_subject_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
