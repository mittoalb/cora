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
does not re-register them. A `SubjectNotFoundError` (or analogous
"missing target" handler) lands here once the first slice that
loads-and-folds the Subject stream ships (4b+); per YAGNI it doesn't
exist yet.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.subject.aggregates.subject import InvalidSubjectNameError
from cora.subject.errors import UnauthorizedError
from cora.subject.features import register_subject


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


def register_subject_routes(app: FastAPI) -> None:
    """Attach Subject slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_subject.router)
    app.add_exception_handler(InvalidSubjectNameError, _handle_invalid_subject_name)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
