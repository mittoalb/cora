"""HTTP setup for the Data BC.

`register_data_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError` and `ConcurrencyError` are infra-layer
errors registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Data
does not re-register them.

## Loop-collapse pattern

Each error family that maps to one HTTP status code with the same
`{"detail": str(exc)}` body shares one generic handler, registered
against a tuple of error classes via a loop. Adding a new error in
a family is one tuple entry, no new handler function. Mirrors every
other BC.

  - 400 (validation): InvalidDatasetNameError, InvalidDatasetUriError,
    InvalidDatasetChecksumError, InvalidDatasetByteSizeError,
    InvalidDatasetFormatError, InvalidDerivedFromError
  - 404: DatasetNotFoundError (via the get_dataset route's HTTPException
    pathway; the Data BC does not register a not-found handler today
    because the read slice handles None directly. Domain code that
    raises DatasetNotFoundError from a handler will trigger the
    handler-level 404 below.)
  - 409 (defensive AlreadyExists): DatasetAlreadyExistsError
  - 409 (cross-aggregate refs): ProducingRunNotFoundError,
    LinkedSubjectNotFoundError, DerivedFromDatasetsNotFoundError
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.data.aggregates.dataset import (
    DatasetAlreadyExistsError,
    DatasetNotFoundError,
    DerivedFromDatasetsNotFoundError,
    InvalidDatasetByteSizeError,
    InvalidDatasetChecksumError,
    InvalidDatasetFormatError,
    InvalidDatasetNameError,
    InvalidDatasetUriError,
    InvalidDerivedFromError,
    LinkedSubjectNotFoundError,
    ProducingRunNotFoundError,
)
from cora.data.errors import UnauthorizedError
from cora.data.features import get_dataset, register_dataset


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
    """Defensive 409 handler for every aggregate's AlreadyExistsError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cross_agg_not_found(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for cross-aggregate-reference not-found errors.

    `register_dataset` accepts optional refs to a Run, a Subject, and
    a set of upstream Datasets. If any referenced aggregate doesn't
    exist, the handler raises one of (ProducingRunNotFoundError,
    LinkedSubjectNotFoundError, DerivedFromDatasetsNotFoundError).
    All three map to 409 because they signal a logical conflict
    (the request is well-formed but inconsistent with the current
    state of the world).
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_data_routes(app: FastAPI) -> None:
    """Attach Data slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_dataset.router)
    app.include_router(get_dataset.router)
    for validation_cls in (
        InvalidDatasetNameError,
        InvalidDatasetUriError,
        InvalidDatasetChecksumError,
        InvalidDatasetByteSizeError,
        InvalidDatasetFormatError,
        InvalidDerivedFromError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (DatasetNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (DatasetAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cross_agg_cls in (
        ProducingRunNotFoundError,
        LinkedSubjectNotFoundError,
        DerivedFromDatasetsNotFoundError,
    ):
        app.add_exception_handler(cross_agg_cls, _handle_cross_agg_not_found)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
