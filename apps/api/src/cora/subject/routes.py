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

## Loop-collapse pattern (cross-BC normalization)

Each error family that maps to one HTTP status code with the same
`{"detail": str(exc)}` body shares one generic handler, registered
against a tuple of error classes via a loop. Adding a new error in
a family is one tuple entry — no new handler function. Mirrors
Equipment / Access; all 4 BCs follow the same shape post-5b cleanup.

The `Cannot<Verb>Error` family for Subject's transition-state
guards (Mount/Measure/Remove/Return/Store/Discard) is the largest
loop in the codebase (6 classes); adding a future transition is one
extra tuple entry.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.subject.aggregates.subject import (
    InvalidSubjectNameError,
    SubjectAlreadyExistsError,
    SubjectCannotDiscardError,
    SubjectCannotMeasureError,
    SubjectCannotMountError,
    SubjectCannotRemoveError,
    SubjectCannotReturnError,
    SubjectCannotStoreError,
    SubjectNotFoundError,
)
from cora.subject.errors import UnauthorizedError
from cora.subject.features import (
    discard_subject,
    get_subject,
    list_subjects,
    measure_subject,
    mount_subject,
    register_subject,
    remove_subject,
    return_subject,
    store_subject,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error (Invalid<X>...)."""
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
    """Shared 409 handler for every state-transition guard.

    Covers Subject's full `SubjectCannot<Verb>Error` family (Mount,
    Measure, Remove, Return, Store, Discard). All transition-state-
    mismatch errors map to the same HTTP 409 + `{"detail": str(exc)}`
    body. Adding a new transition is one extra entry in the tuple.
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
    app.include_router(return_subject.router)
    app.include_router(store_subject.router)
    app.include_router(discard_subject.router)
    app.include_router(get_subject.router)
    app.include_router(list_subjects.router)
    for validation_cls in (InvalidSubjectNameError,):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (SubjectNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (SubjectAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        SubjectCannotMountError,
        SubjectCannotMeasureError,
        SubjectCannotRemoveError,
        SubjectCannotReturnError,
        SubjectCannotStoreError,
        SubjectCannotDiscardError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
